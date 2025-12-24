from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi_mqtt import FastMQTT, MQTTConfig
import json
import uvicorn
from pathlib import Path
from collections import defaultdict

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        # Dictionary to hold lists of websockets for each vehicle_id
        # Structure: {'nandi_1': [ws1, ws2], 'nandi_2': [ws3]}
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, vehicle_id: str):
        await websocket.accept()
        self.active_connections[vehicle_id].append(websocket)

    def disconnect(self, websocket: WebSocket, vehicle_id: str):
        if vehicle_id in self.active_connections:
            if websocket in self.active_connections[vehicle_id]:
                self.active_connections[vehicle_id].remove(websocket)

    async def broadcast_to_vehicle(self, data: dict, vehicle_id: str):
        """Sends data only to clients viewing the specific vehicle_id"""
        if vehicle_id not in self.active_connections:
            return

        dead = []
        text = json.dumps(data)
        
        # Only iterate over sockets connected to this specific vehicle
        for ws in self.active_connections[vehicle_id]:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        
        for ws in dead:
            self.disconnect(ws, vehicle_id)

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
    # SUBSCRIBE using wildcard '+' to get data for ALL vehicles
    # This matches 'vehicle/nandi_1/data', 'vehicle/nandi_2/data', etc.
    mqtt.client.subscribe("vehicle/+/data")

@mqtt.on_message()
async def handle_message(client, topic, payload, qos, properties):
    try:
        # Topic format: vehicle/{vehicle_id}/data
        # We extract the vehicle_id from the topic string
        parts = topic.split('/')
        if len(parts) >= 2:
            target_vehicle_id = parts[1] # e.g., 'nandi_1' or 'nandi_2'
            
            data = json.loads(payload.decode())
            
            # Optional: Print logs only for active listeners to reduce noise
            if target_vehicle_id in manager.active_connections and manager.active_connections[target_vehicle_id]:
                 print(f"📍 MQTT [{target_vehicle_id}]: Speed={data.get('signals', {}).get('Speed', 0)}")
            
            # Route data to the correct WebSocket group
            await manager.broadcast_to_vehicle(data, target_vehicle_id)
            
    except Exception as e:
        print(f"❌ MQTT parse error: {e}")

# --- HTTP + WebSocket endpoints ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Updated endpoint to accept vehicle_id
@app.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_ws(websocket: WebSocket, vehicle_id: str):
    await manager.connect(websocket, vehicle_id)
    try:
        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, vehicle_id)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)