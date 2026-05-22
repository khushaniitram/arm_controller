from fastapi import WebSocket
from robot.robot_manager import robot
import json

class ConnectionManager:

    def __init__(self):
        self.active_connections=[]

    async def connect(self, websocket: WebSocket):

        await websocket.accept()

        self.active_connections.append(
            websocket
        )

        print(
            "✓ WebSocket connected"
        )


    def disconnect(self, websocket):

        self.active_connections.remove(
            websocket
        )

        print(
            "⚠ WebSocket disconnected"
        )


manager=ConnectionManager()


async def handle_websocket(
    websocket: WebSocket
):

    await manager.connect(
        websocket
    )

    try:

        while True:

            data=await websocket.receive_text()

            data=json.loads(data)

            command=data.get(
                "command"
            )

            if command=="joint":

                robot.jog_joint(
                    data["joint"],
                    data["direction"]
                )

            elif command=="cartesian":

                robot.jog_cartesian(
                    data["axis"],
                    data["direction"]
                )

            elif command == "stop":
                robot.stop()

            elif command == "speed":
                robot.set_speed(data["speed"])


            feedback=robot.read_feedback()

            await websocket.send_json({
                "type":"feedback",
                "data":feedback
            })

    except:

        manager.disconnect(
            websocket
        )