from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi_mqtt import FastMQTT, MQTTConfig
import json
import uvicorn
from pathlib import Path
from collections import defaultdict
import csv
import os
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# --- CSV Logging Setup ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def save_to_csv(vehicle_id, data):
    """Saves telemetry data to a daily CSV file."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{LOG_DIR}/{today}_{vehicle_id}.csv"
        file_exists = os.path.isfile(filename)

        # Extract relevant fields (Flattening the JSON)
        # Use server time if timestamp is missing in payload
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        gnss = data.get('gnss', {}) or data.get('location', {})
        signals = data.get('signals', {}) or data
        
        lat = gnss.get('lat') or gnss.get('latitude')
        lon = gnss.get('lon') or gnss.get('longitude')
        
        # Define the row data
        row = {
            "timestamp": timestamp,
            "vehicle_id": vehicle_id,
            "lat": lat,
            "lon": lon,
            "speed": signals.get('Speed'),
            "soc": signals.get('RSOC') or signals.get('ActualSocPercentage') or signals.get('SOC'),
            "battery_energy": signals.get('BatteryEnergy'),
            "rpm": signals.get('RPM'),
            "odometer": signals.get('Main_Odometer'),
            "direction": data.get('vehicle_direction_deg')
        }

        # Write to CSV
        with open(filename, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
            
    except Exception as e:
        print(f"❌ CSV Error: {e}")

# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, vehicle_id: str):
        await websocket.accept()
        self.active_connections[vehicle_id].append(websocket)

    def disconnect(self, websocket: WebSocket, vehicle_id: str):
        if vehicle_id in self.active_connections:
            if websocket in self.active_connections[vehicle_id]:
                self.active_connections[vehicle_id].remove(websocket)

    async def broadcast_to_vehicle(self, data: dict, vehicle_id: str):
        if vehicle_id not in self.active_connections: return
        dead = []
        text = json.dumps(data)
        for ws in self.active_connections[vehicle_id]:
            try: await ws.send_text(text)
            except Exception: dead.append(ws)
        for ws in dead: self.disconnect(ws, vehicle_id)

manager = ConnectionManager()

# --- MQTT setup ---
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
            target_vehicle_id = parts[1]
            data = json.loads(payload.decode())
            
            # 1. Log to CSV
            save_to_csv(target_vehicle_id, data)
            
            # 2. Broadcast to WebSockets
            if target_vehicle_id in manager.active_connections:
                 print(f"📍 MQTT [{target_vehicle_id}]")
            await manager.broadcast_to_vehicle(data, target_vehicle_id)
            
    except Exception as e:
        print(f"❌ MQTT parse error: {e}")

# --- HTTP + WebSocket endpoints ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/history/{vehicle_id}")
async def get_history(vehicle_id: str):
    """Returns the path history (lat, lon) for the selected vehicle today."""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{LOG_DIR}/{today}_{vehicle_id}.csv"
    path = []
    
    if os.path.exists(filename):
        try:
            with open(filename, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Only add if valid lat/lon exist
                    if row.get('lat') and row.get('lon'):
                        try:
                            lat = float(row['lat'])
                            lon = float(row['lon'])
                            path.append([lat, lon])
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Error reading history: {e}")
            
    return JSONResponse(content={"path": path})

@app.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_ws(websocket: WebSocket, vehicle_id: str):
    await manager.connect(websocket, vehicle_id)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, vehicle_id)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)