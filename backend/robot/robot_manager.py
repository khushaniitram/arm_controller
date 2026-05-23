from config import (
    ROBOT_AUTO_DETECT,
    ROBOT_BAUDRATE,
    ROBOT_MIN_MOTION_INTERVAL,
    ROBOT_PORT,
    ROBOT_RECONNECT_INTERVAL,
    ROBOT_SERIAL_STARTUP_DELAY,
)

from .teensy_robot import TeensyRobot


class RobotManager:
    def __init__(self):
        print("\n" + "=" * 40)
        print("AR4 SYSTEM STARTING")
        print("=" * 40)
        print("\n[1/4] Initializing Robot...")

        if ROBOT_PORT:
            print(f"Configured robot serial port: {ROBOT_PORT}")
        elif ROBOT_AUTO_DETECT:
            print("Robot serial port: auto-detect enabled")
        else:
            print("Robot serial port not set and auto-detect disabled")

        self.robot = TeensyRobot(
            port=ROBOT_PORT,
            baudrate=ROBOT_BAUDRATE,
            auto_detect=ROBOT_AUTO_DETECT,
            startup_delay=ROBOT_SERIAL_STARTUP_DELAY,
            reconnect_interval=ROBOT_RECONNECT_INTERVAL,
            min_motion_interval=ROBOT_MIN_MOTION_INTERVAL,
        )
        print(f"Robot mode: {self.robot.mode}")
        print(f"Robot reconnect interval: {ROBOT_RECONNECT_INTERVAL}s")


manager = RobotManager()
robot = manager.robot
