from abc import ABC, abstractmethod
import threading
import time

class BaseRobot(ABC):

    @abstractmethod
    def jog_joint(self,joint,direction):
        pass

    @abstractmethod
    def jog_cartesian(self,axis,direction):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def set_speed(self,speed):
        pass

    @abstractmethod
    def read_feedback(self):
        pass

    def move_to_coords(self, target_x, target_y):
        if not hasattr(self, "_cancel_move"):
            self._cancel_move = False
        if not hasattr(self, "_move_thread"):
            self._move_thread = None

        self.cancel_move_to()
        self._cancel_move = False
        self._move_thread = threading.Thread(
            target=self._move_to_coords_loop,
            args=(target_x, target_y),
            daemon=True
        )
        self._move_thread.start()

    def cancel_move_to(self):
        self._cancel_move = True

    def is_moving_to_coords(self):
        return bool(
            hasattr(self, "_move_thread")
            and self._move_thread
            and self._move_thread.is_alive()
            and not getattr(self, "_cancel_move", False)
        )

    def _move_to_coords_loop(self, target_x, target_y):
        time.sleep(0.01)
        min_interval = getattr(self, "min_motion_interval", 0.2)
        
        # Move X axis first
        while not self._cancel_move:
            feedback = self.read_feedback()
            if not feedback.get("connected", True):
                break

            current_x = self.position.get("x", 0.0)
            dx = target_x - current_x
            if abs(dx) < 0.1:
                break
            direction = "+" if dx > 0 else "-"
            self.jog_cartesian("X", direction)
            time.sleep(min_interval + 0.05)

        # Move Y axis next
        while not self._cancel_move:
            feedback = self.read_feedback()
            if not feedback.get("connected", True):
                break

            current_y = self.position.get("y", 0.0)
            dy = target_y - current_y
            if abs(dy) < 0.1:
                break
            direction = "+" if dy > 0 else "-"
            self.jog_cartesian("Y", direction)
            time.sleep(min_interval + 0.05)

        # Stop robot when done
        self.stop()