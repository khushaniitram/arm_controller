import asyncio
import json

from fastapi import WebSocket
from robot.robot_manager import robot


class ConnectionManager:
    def __init__(self):
        self.active_connections = []
        self._locks = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self._locks[websocket] = asyncio.Lock()
        print("WebSocket connected")

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self._locks.pop(websocket, None)
        print("WebSocket disconnected")

    async def send_json_safe(self, websocket: WebSocket, data: dict):
        lock = self._locks.get(websocket)
        if lock:
            async with lock:
                try:
                    await websocket.send_json(data)
                except Exception:
                    pass


manager = ConnectionManager()


async def _handle_command(data):
    command = data.get("command")

    if command == "joint":
        joint = int(data["joint"])
        direction = data["direction"]
        if data.get("lock_needle") and joint >= 4:
            needle_len = float(data.get("needle_length", 50.0))
            robot.jog_joint_locked(joint, direction, needle_len)
        else:
            robot.jog_joint(joint, direction)
    elif command == "cartesian":
        robot.jog_cartesian(str(data["axis"]), data["direction"])
    elif command == "stop":
        if data.get("lock_needle"):
            needle_len = float(data.get("needle_length", 50.0))
            robot.stop_locked(needle_len)
        else:
            robot.stop()
    elif command == "speed":
        robot.set_speed(int(data["speed"]))
    elif command == "move_to":
        robot.move_to_coords(float(data["x"]), float(data["y"]))
    else:
        raise ValueError(f"Unknown command: {command}")


async def telemetry_broadcaster(websocket: WebSocket):
    try:
        while True:
            feedback = robot.read_feedback()
            await manager.send_json_safe(websocket, {"type": "feedback", "data": feedback})
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def handle_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    broadcaster_task = asyncio.create_task(telemetry_broadcaster(websocket))

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await manager.send_json_safe(
                    websocket, {"type": "error", "message": "Invalid JSON payload"}
                )
                continue

            try:
                await _handle_command(data)
                feedback = robot.read_feedback()
                response = {"type": "feedback", "data": feedback}
                if "timestamp" in data:
                    response["timestamp"] = data["timestamp"]
                await manager.send_json_safe(websocket, response)
            except Exception as exc:
                await manager.send_json_safe(websocket, {"type": "error", "message": str(exc)})

    except Exception:
        manager.disconnect(websocket)
    finally:
        try:
            robot.stop()
        except Exception:
            pass
        broadcaster_task.cancel()
