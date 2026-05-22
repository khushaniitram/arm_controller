from .teensy_robot import TeensyRobot

class RobotManager:

    def __init__(self):

        print("\n"+"="*40)
        print("AR4 SYSTEM STARTING")
        print("="*40)

        print("\n[1/4] Initializing Robot...")

        self.robot = TeensyRobot(port="COM4")

        print("✓ Robot Ready")


manager = RobotManager()

robot = manager.robot