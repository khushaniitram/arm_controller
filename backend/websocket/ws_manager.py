import json

from fastapi import WebSocket
from robot.robot_manager import robot


class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print("WebSocket connected")

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print("WebSocket disconnected")


manager = ConnectionManager()


async def _handle_command(data):
    command = data.get("command")

    if command == "joint":
        robot.jog_joint(int(data["joint"]), data["direction"])
    elif command == "cartesian":
        robot.jog_cartesian(str(data["axis"]), data["direction"])
    elif command == "stop":
        robot.stop()
    elif command == "speed":
        robot.set_speed(int(data["speed"]))
    else:
        raise ValueError(f"Unknown command: {command}")


async def handle_websocket(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "message": "Invalid JSON payload"}
                )
                continue

            try:
                await _handle_command(data)
                feedback = robot.read_feedback()
                await websocket.send_json({"type": "feedback", "data": feedback})
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})

    except Exception:
        manager.disconnect(websocket)
