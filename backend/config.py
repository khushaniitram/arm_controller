import os


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_origins_env() -> list[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


ROBOT_PORT = os.getenv("ROBOT_PORT") or os.getenv("ROBOT_SERIAL_PORT")
ROBOT_BAUDRATE = int(os.getenv("ROBOT_BAUDRATE", "9600"))
ROBOT_AUTO_DETECT = _read_bool_env("ROBOT_AUTO_DETECT", True)
ROBOT_SERIAL_STARTUP_DELAY = float(os.getenv("ROBOT_SERIAL_STARTUP_DELAY", "2.0"))
ROBOT_RECONNECT_INTERVAL = float(os.getenv("ROBOT_RECONNECT_INTERVAL", "2.0"))
ROBOT_MIN_MOTION_INTERVAL = float(os.getenv("ROBOT_MIN_MOTION_INTERVAL", "0.2"))

raw_camera_index = os.getenv("CAMERA_INDEX")
if raw_camera_index is not None:
    try:
        CAMERA_INDEX = int(raw_camera_index)
    except ValueError:
        CAMERA_INDEX = 0
else:
    CAMERA_INDEX = None

ALLOWED_ORIGINS = _read_origins_env()
