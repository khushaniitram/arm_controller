from fastapi import FastAPI
from robot.robot_manager import robot
from fastapi import WebSocket
from websocket.ws_manager import handle_websocket
from camera.camera_manager import camera_manager
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription
from pydantic import BaseModel
import asyncio
from config import ALLOWED_ORIGINS
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
async def home():
    return {
        "status":"running"
    }

@app.get("/position")
async def position():
    return robot.read_feedback()

@app.get("/camera/status")
async def camera_status():
    return camera_manager.get_status()

@app.post("/joint/{joint}/{direction}")
async def joint(
    joint:int,
    direction:str
):

    robot.jog_joint(
        joint,
        direction
    )

    return {
        "ok":True
    }

@app.post("/cartesian/{axis}/{direction}")
async def cartesian(
    axis:str,
    direction:str
):

    robot.jog_cartesian(
        axis,
        direction
    )

    return {
        "ok":True
    }

@app.post("/stop")
async def stop():

    robot.stop()

    return {
        "ok":True
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket:WebSocket
):

    await handle_websocket(
        websocket
    )

class Offer(BaseModel):
    sdp: str
    type: str

pcs = set()

@app.on_event("startup")
async def on_startup():
    robot.start()

@app.on_event("shutdown")
async def on_shutdown():
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    robot.close()

@app.post("/offer")
async def offer(params: Offer):
    offer = RTCSessionDescription(sdp=params.sdp, type=params.type)

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)

    # Add camera track
    pc.addTrack(camera_manager.get_track())

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
