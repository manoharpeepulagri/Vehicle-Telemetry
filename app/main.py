from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi_mqtt import FastMQTT, MQTTConfig
import json
import uvicorn
from pathlib import Path
from collections import defaultdict
import csv
import os
import math
from datetime import datetime, timedelta

app = FastAPI()

# --- 1. CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# --- Logging Setup ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Throttling tracker for stress logs
stress_log_tracker = defaultdict(lambda: datetime.min)

def cleanup_old_logs():
    """Deletes logs that do not match today's date."""
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        for filename in os.listdir(LOG_DIR):
            if filename.endswith(".csv") and "stress_events" not in filename:
                if not filename.startswith(today_str):
                    try:
                        os.remove(os.path.join(LOG_DIR, filename))
                    except: pass
    except Exception as e:
        print(f"Cleanup Error: {e}")

def save_to_csv(vehicle_id, data):
    """Saves telemetry data including spray status."""
    try:
        cleanup_old_logs()

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{LOG_DIR}/{today}_{vehicle_id}.csv"
        file_exists = os.path.isfile(filename)

        gnss = data.get('gnss', {}) or data.get('location', {})
        signals = data.get('signals', {}) or data
        
        row = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "lat": gnss.get('lat'),
            "lon": gnss.get('lon'),
            "speed": signals.get('Speed'),
            "soc": signals.get('RSOC') or signals.get('ActualSocPercentage') or signals.get('SOC'),
            "battery_energy": signals.get('BatteryEnergy'),
            "current": signals.get('Battery_current'),
            "motor_temp": signals.get('Tr_Mtr_Temp'),
            "motor_current": signals.get('Mtr_RMS_currents'),
            "odometer": signals.get('Main_Odometer'),
            "gear_low": signals.get('Gear_Low'),
            "travel_mode": signals.get('Travel_Mode'),
            "field_mode": signals.get('Field_Mode'),
            "spray_status": signals.get('Spray_Pump_Status', 0)
        }

        with open(filename, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists: writer.writeheader()
            writer.writerow(row)
            
    except Exception as e:
        print(f"❌ CSV Error: {e}")

def check_stress_events(vehicle_id, data):
    """Logs stress events (throttled)."""
    try:
        signals = data.get('signals', {}) or data
        motor_current = signals.get('Mtr_RMS_currents') or 0
        motor_temp = signals.get('Tr_Mtr_Temp') or 0
        
        if motor_current > 80 or motor_temp > 80:
            last_log = stress_log_tracker[vehicle_id]
            if datetime.now() - last_log < timedelta(seconds=60):
                return

            stress_log_tracker[vehicle_id] = datetime.now()
            
            filename = f"{LOG_DIR}/stress_events.csv"
            file_exists = os.path.isfile(filename)
            
            row = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M:%S"),
                "vehicle_id": vehicle_id,
                "reason": [],
                "value_current": motor_current,
                "value_temp": motor_temp
            }
            if motor_current > 80: row['reason'].append("High Current")
            if motor_temp > 80: row['reason'].append("Overheat")
            row['reason'] = " & ".join(row['reason'])

            with open(filename, mode='a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists: writer.writeheader()
                writer.writerow(row)
                print(f"⚠️ STRESS EVENT [{vehicle_id}]: {row['reason']}")
    except: pass

# --- Calculations ---
def calculate_distances(points):
    """
    Calculates total distance AND spray distance.
    points: list of [lat, lon, spray_status]
    """
    total_km = 0.0
    spray_km = 0.0
    R = 6371  # Earth radius km

    for i in range(len(points) - 1):
        lat1, lon1, s1 = points[i]
        lat2, lon2, s2 = points[i+1]

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        if distance > 0.0005: # Noise filter 0.5m
            total_km += distance
            try:
                if int(float(s1)) == 1: 
                    spray_km += distance
            except:
                pass

    return round(total_km, 3), round(spray_km, 3)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, vehicle_id: str):
        await websocket.accept()
        self.active_connections[vehicle_id].append(websocket)
        print(f"✅ WebSocket connected for vehicle: {vehicle_id}")

    def disconnect(self, websocket: WebSocket, vehicle_id: str):
        if vehicle_id in self.active_connections:
            if websocket in self.active_connections[vehicle_id]:
                self.active_connections[vehicle_id].remove(websocket)
                print(f"❌ WebSocket disconnected for vehicle: {vehicle_id}")

    async def broadcast_to_vehicle(self, data: dict, vehicle_id: str):
        if vehicle_id not in self.active_connections: 
            return
        text = json.dumps(data)
        dead = []
        for ws in self.active_connections[vehicle_id]:
            try: 
                await ws.send_text(text)
            except: 
                dead.append(ws)
        for ws in dead: 
            self.disconnect(ws, vehicle_id)

manager = ConnectionManager()

# --- MQTT Setup ---
mqtt_config = MQTTConfig(
    host="w8e06e1d.ala.asia-southeast1.emqxsl.com",
    port=8883,
    keepalive=60,
    username="PRUDHVI",
    password="PRUDHVI",
    ssl=True,
    client_id="CAN_LOGGER_SERVER_001",
)
mqtt = FastMQTT(config=mqtt_config)
mqtt.init_app(app)

@mqtt.on_connect()
def handle_connect(client, flags, rc, properties):
    print("✅ MQTT Connected")
    mqtt.client.subscribe("vehicle/+/data")

@mqtt.on_message()
async def handle_message(client, topic, payload, qos, properties):
    try:
        parts = topic.split('/')
        if len(parts) >= 2:
            vid = parts[1]
            data = json.loads(payload.decode())
            
            # CRITICAL: Stamp data with vehicle_id for filtering
            data['vehicle_id'] = vid
            
            print(f"📨 Message from {vid}: {list(data.keys())}")
            
            await run_in_threadpool(save_to_csv, vid, data)
            await run_in_threadpool(check_stress_events, vid, data)
            
            # Broadcast to all connected clients of this vehicle
            await manager.broadcast_to_vehicle(data, vid)
    except Exception as e:
        print(f"❌ MQTT Error: {e}")

# --- Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_ws(websocket: WebSocket, vehicle_id: str):
    await manager.connect(websocket, vehicle_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, vehicle_id)
    except Exception as e:
        print(f"❌ WebSocket Error: {e}")
        manager.disconnect(websocket, vehicle_id)

@app.get("/history/{vehicle_id}")
async def get_history(vehicle_id: str):
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{LOG_DIR}/{today}_{vehicle_id}.csv"
    path = []
    
    if os.path.exists(filename):
        try:
            with open(filename, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('lat') and row.get('lon'):
                        try:
                            lat = float(row['lat'])
                            lon = float(row['lon'])
                            spray = float(row.get('spray_status', 0))
                            path.append([lat, lon, spray])
                        except: 
                            continue
        except Exception as e:
            print(f"❌ History read error: {e}")
    
    # Calculate Distances
    total, spray = calculate_distances(path)

    return JSONResponse(content={
        "path": path,
        "gps_distance_km": total,
        "spray_distance_km": spray
    })

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)