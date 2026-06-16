import asyncio
import os
import threading
import time

# Silence OpenCV log spam (warning and error messages) in the console
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

import cv2
import numpy as np
from aiortc import VideoStreamTrack
from aiortc.contrib.media import MediaRelay
from av import VideoFrame
from config import CAMERA_INDEX


class CameraTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, camera_manager):
        super().__init__()
        self.camera_manager = camera_manager

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.camera_manager.get_frame()

        if frame is None:
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
        self.selected_index = None
        self.last_frame_at = None
        self.last_error = None

        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()

    def get_track(self):
        if self.track is None:
            self.track = CameraTrack(self)
        return self.relay.subscribe(self.track)

    def init_camera(self, silent=False):
        if not silent:
            print("\n[2/5] Initializing Camera...")

        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY

        # If a specific camera index is forced, use it directly
        if CAMERA_INDEX is not None:
            cap = cv2.VideoCapture(CAMERA_INDEX, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                self.camera = cap
                self.selected_index = CAMERA_INDEX
                self.last_error = None
                print(f"[OK] Camera connected on forced index {CAMERA_INDEX}")
                self.connected = True
                return True
            else:
                try:
                    cap.release()
                except:
                    pass
                if not silent:
                    print(f"[ERR] Failed to open forced camera index {CAMERA_INDEX}")
                self.last_error = f"Failed to open forced camera index {CAMERA_INDEX}"
                return False

        # Otherwise, run auto-detection probing
        available_cameras = []
        for idx in [0, 1, 2, 3]:
            cap = cv2.VideoCapture(idx, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                success, frame = cap.read()
                if success and frame is not None:
                    available_cameras.append((idx, cap))
                else:
                    cap.release()
            else:
                try:
                    cap.release()
                except:
                    pass

        if not available_cameras:
            if not silent:
                print("[ERR] No working camera found.")
            self.last_error = "No working camera found"
            return False

        # Prefer external cameras (index >= 1), otherwise fall back to index 0 (built-in)
        selected_idx, selected_cap = available_cameras[0]
        for idx, cap in available_cameras:
            if idx >= 1:
                selected_idx = idx
                selected_cap = cap
                break

        # Release any other cameras that were opened during probing
        for idx, cap in available_cameras:
            if idx != selected_idx:
                cap.release()

        self.camera = selected_cap
        self.selected_index = selected_idx
        self.last_error = None
        print(f"[OK] Camera connected on index {selected_idx}")
        self.connected = True
        return True

    def update(self):
        last_logged_connected = None
        while self.running:
            if self.camera is None or not self.camera.isOpened():
                if self.connected:
                    print("[WARN] Camera disconnected")
                self.connected = False
                self.selected_index = None

                # If we previously logged connected (or haven't logged yet), print disconnected once.
                if last_logged_connected is not False:
                    print("[ERR] Camera not connected")
                    last_logged_connected = False

                if self.init_camera(silent=True):
                    print("[OK] Stream ready")
                    last_logged_connected = True
                else:
                    time.sleep(2)
                    continue

            success, frame = self.camera.read()
            if success:
                self.frame = frame
                self.last_frame_at = time.time()
            else:
                if last_logged_connected is not False:
                    print("[WARN] Could not grab frame. Reinitializing...")
                    last_logged_connected = False
                self.camera.release()
                self.connected = False
                self.selected_index = None
                self.frame = None
                self.last_error = "Could not grab frame"
                time.sleep(1)

    def get_frame(self):
        return self.frame

    def get_status(self):
        return {
            "connected": self.connected,
            "camera_index": self.selected_index,
            "has_frame": self.frame is not None,
            "last_frame_age_ms": (
                round((time.time() - self.last_frame_at) * 1000.0)
                if self.last_frame_at
                else None
            ),
            "error": self.last_error,
        }


camera_manager = CameraManager()
