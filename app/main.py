from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi_mqtt import FastMQTT, MQTTConfig
import asyncio
import json
import ssl
import uvicorn
from pathlib import Path

app = FastAPI()

# Add CORS and compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        # map vehicle_id -> list[WebSocket]
        self.vehicle_connections: dict[str, list[WebSocket]] = {}
        # connections that want all vehicle updates
        self.all_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, vehicle_id: str):
        await websocket.accept()
        if vehicle_id == "all":
            self.all_connections.append(websocket)
        else:
            self.vehicle_connections.setdefault(vehicle_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            if websocket in self.all_connections:
                self.all_connections.remove(websocket)
        except ValueError:
            pass
        for lst in list(self.vehicle_connections.values()):
            try:
                if websocket in lst:
                    lst.remove(websocket)
            except ValueError:
                pass

    async def broadcast_json(self, data: dict, vehicle_id: str | None = None):
        # send concurrently with a short timeout per socket to avoid blocking
        text = json.dumps(data)
        targets: list[WebSocket] = []
        if vehicle_id and vehicle_id in self.vehicle_connections:
            targets.extend(list(self.vehicle_connections[vehicle_id]))
        targets.extend(list(self.all_connections))
        if not targets:
            return
        send_tasks = [self._safe_send(ws, text) for ws in targets]
        await asyncio.gather(*send_tasks)

    async def _safe_send(self, ws: WebSocket, text: str, timeout: float = 2.0):
        try:
            await asyncio.wait_for(ws.send_text(text), timeout=timeout)
        except Exception:
            try:
                self.disconnect(ws)
            except Exception:
                pass

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
    # subscribe to all vehicle data topics (vehicle/<vehicle_id>/data)
    mqtt.client.subscribe("vehicle/+/data")

@mqtt.on_message()
async def handle_message(client, topic, payload, qos, properties):
    try:
        data = json.loads(payload.decode())
    except Exception as e:
        print(f"❌ MQTT parse error: {e}")
        return
    # extract vehicle id from topic like: vehicle/<vehicle_id>/data
    vehicle_id = None
    try:
        parts = topic.split('/')
        if len(parts) >= 3:
            vehicle_id = parts[1]
    except Exception:
        vehicle_id = None
    print(f"📍 MQTT: vehicle={vehicle_id}, lat={data.get('gnss', {}).get('lat')}, speed={data.get('signals', {}).get('Speed')}")
    await manager.broadcast_json(data, vehicle_id)

# --- HTTP + WebSocket endpoints ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_ws(websocket: WebSocket, vehicle_id: str):
    await manager.connect(websocket, vehicle_id)
    try:
        while True:
            # keep the connection alive; client may optionally send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)