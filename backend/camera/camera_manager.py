import cv2
import threading
import time
import asyncio
import numpy as np
from aiortc import VideoStreamTrack
from aiortc.contrib.media import MediaRelay
from av import VideoFrame

class CameraTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, camera_manager):
        super().__init__()
        self.camera_manager = camera_manager

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.camera_manager.get_frame()
        
        if frame is None:
            # Return a black frame if no frame is available
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            await asyncio.sleep(0.03)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

class CameraManager:
    def __init__(self):
        self.frame = None
        self.camera = None
        self.running = True
        self.connected = False
        self.relay = MediaRelay()
        self.track = None
        
        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()

    def get_track(self):
        if self.track is None:
            self.track = CameraTrack(self)
        return self.relay.subscribe(self.track)

    def init_camera(self):
        print("\n[2/5] Initializing Camera...")
        
        # Try indices 1, 2, 3 first (usually external/USB cameras), fallback to 0 (usually built-in)
        for idx in [1, 2, 3, 0]:
            print(f"Trying camera index {idx}...")
            # Use CAP_DSHOW explicitly to prevent obsensor backend errors on Windows
            self.camera = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            
            if self.camera.isOpened():
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_FPS, 30)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Verify we can actually read a frame
                success = False
                for _ in range(5):
                    success, frame = self.camera.read()
                    if success and frame is not None:
                        break
                    time.sleep(0.1)
                    
                if success:
                    print(f"✓ Camera Connected on index {idx}")
                    self.connected = True
                    return True
                else:
                    print(f"✗ Camera {idx} opened but could not read frames.")
                    self.camera.release()
            else:
                print(f"✗ Camera {idx} not found or failed to open.")

        print("✗ No working camera found.")
        return False

    def update(self):
        while self.running:
            if self.camera is None or not self.camera.isOpened():
                if self.connected:
                    print("⚠ Camera Disconnected")
                self.connected = False
                
                if self.init_camera():
                    print("✓ Stream Ready")
                else:
                    time.sleep(2)
                    continue
                    
            success, frame = self.camera.read()
            if success:
                self.frame = frame
            else:
                print("⚠ Could not grab frame. Reinitializing...")
                self.camera.release()
                self.connected = False
                self.frame = None
                time.sleep(1)

    def get_frame(self):
        return self.frame

camera_manager = CameraManager()