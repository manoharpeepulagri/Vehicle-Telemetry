from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi_mqtt import FastMQTT, MQTTConfig
import json
import ssl
import uvicorn
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, data: dict):
        dead = []
        text = json.dumps(data)
        for ws in self.active_connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

# --- MQTT setup ---
mqtt_config = MQTTConfig(
    host="w8e06e1d.ala.asia-southeast1.emqxsl.com",
    port=8883,
    keepalive=60,
    username="PRUDHVI",
    password="PRUDHVI",
    ssl=True,  # let fastapi-mqtt create default TLS context
    client_id="CAN_LOGGER_001",
)

mqtt = FastMQTT(config=mqtt_config)
mqtt.init_app(app)

@mqtt.on_connect()
def handle_connect(client, flags, rc, properties):
    # subscribe to your data topic
    mqtt.client.subscribe("vehicle/nandi_2/data")

@mqtt.on_message()
async def handle_message(client, topic, payload, qos, properties):
    try:
        data = json.loads(payload.decode())
        print(f"📍 MQTT: lat={data.get('gnss', {}).get('lat')}, speed={data['signals'].get('Speed')}")
        await manager.broadcast_json(data)
    except Exception as e:
        print(f"❌ MQTT parse error: {e}")

# --- HTTP + WebSocket endpoints ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/vehicle")
async def vehicle_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # backend pushes; client doesn't need to send
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
#if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)