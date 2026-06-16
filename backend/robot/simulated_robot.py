from .base_robot import BaseRobot

class SimulatedRobot(BaseRobot):

    def __init__(self):

        self.speed=25

        self.position={

            "x":0,
            "y":0,
            "z":0,

            "j1":0,
            "j2":0,
            "j3":0,
            "j4":0,
            "j5":0,
            "j6":0
        }

        print("✓ Simulation Robot Loaded")


    def jog_joint(self,joint,direction):

        amount=1 if direction=="+" else -1

        self.position[f"j{joint}"]+=amount

        print(
            f"Joint {joint} {direction}"
        )


    def jog_cartesian(self,axis,direction):

        amount=1 if direction=="+" else -1

        axis=axis.lower()

        self.position[axis]+=amount

        print(
            f"{axis}:{direction}"
        )


    def stop(self):
        self.cancel_move_to()
        self._tracker_running = False
        self._active_jog_joint = None
        self._active_jog_dir = None
        print(
            "Robot stopped"
        )


    def set_speed(self,speed):

        self.speed=speed

        print(
            f"Speed:{speed}"
        )


    def read_feedback(self):
        feedback = self.position.copy()
        feedback["mode"] = "Simulation Mode"
        feedback["connected"] = True
        feedback["moving_to_coords"] = self.is_moving_to_coords()
        return feedback