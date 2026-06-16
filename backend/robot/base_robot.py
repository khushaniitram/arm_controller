from abc import ABC, abstractmethod
import threading
import time
import math

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

    def start(self):
        pass

    def _get_tool_vector(self, j1, j2, j3, j4, j5):
        # 1 unit step is treated as 1 degree of rotation in joint space
        scale = math.radians(1.0)
        q1 = j1 * scale
        q2 = j2 * scale
        q3 = j3 * scale
        q4 = j4 * scale
        q5 = j5 * scale
        
        # Cosines and Sines
        c1, s1 = math.cos(q1), math.sin(q1)
        q23 = q2 + q3
        c23, s23 = math.cos(q23), math.sin(q23)
        c4, s4 = math.cos(q4), math.sin(q4)
        c5, s5 = math.cos(q5), math.sin(q5)
        
        # Base to wrist center orientation (rotation matrix columns)
        r00 = c1 * c23
        r01 = -s1
        r02 = c1 * s23
        
        r10 = s1 * c23
        r11 = c1
        r12 = s1 * s23
        
        r20 = -s23
        r21 = 0
        r22 = c23
        
        # Tool offset vector relative to the wrist frame
        t_x = s5
        t_y = -s4 * c5
        t_z = c4 * c5
        
        # Transform tool vector to base coordinates
        z_x = r00 * t_x + r01 * t_y + r02 * t_z
        z_y = r10 * t_x + r11 * t_y + r12 * t_z
        z_z = r20 * t_x + r21 * t_y + r22 * t_z
        
        return z_x, z_y, z_z

    def jog_joint_locked(self, joint, direction, needle_length=50.0):
        # If tracker thread is not running, initialize the tracking state
        if not getattr(self, "_tracker_running", False):
            self._tracker_running = True
            self._active_jog_joint = joint
            self._active_jog_dir = direction
            self._lock_needle_active = True
            self._lock_needle_start_pos = self.position.copy()
            
            # Compute starting tool tip position
            j1 = self.position.get("j1", 0.0)
            j2 = self.position.get("j2", 0.0)
            j3 = self.position.get("j3", 0.0)
            j4 = self.position.get("j4", 0.0)
            j5 = self.position.get("j5", 0.0)
            vx, vy, vz = self._get_tool_vector(j1, j2, j3, j4, j5)
            self._lock_needle_tip_start = {
                "x": self.position["x"] + needle_length * vx,
                "y": self.position["y"] + needle_length * vy,
                "z": self.position["z"] + needle_length * vz,
            }
            
            # Start the tracker loop thread
            tracker_thread = threading.Thread(
                target=self._jog_tracker_loop,
                args=(needle_length,),
                daemon=True
            )
            tracker_thread.start()
            
        # Send physical jog command to Teensy
        self.jog_joint(joint, direction)

    def _jog_tracker_loop(self, needle_length):
        interval = 0.05 # 50ms update interval
        
        while getattr(self, "_tracker_running", False) and getattr(self, "_active_jog_joint", None) is not None:
            joint = self._active_jog_joint
            direction = self._active_jog_dir
            
            # 1 unit per degree. Estimate degrees/sec based on speed setting
            speed = getattr(self, "speed", 25)
            step_deg = (speed * 0.4) * interval
            if direction == "-":
                step_deg = -step_deg
                
            # Update joint position
            self.position[f"j{joint}"] += step_deg
            
            # Calculate new tool vector
            j1 = self.position.get("j1", 0.0)
            j2 = self.position.get("j2", 0.0)
            j3 = self.position.get("j3", 0.0)
            j4 = self.position.get("j4", 0.0)
            j5 = self.position.get("j5", 0.0)
            vx, vy, vz = self._get_tool_vector(j1, j2, j3, j4, j5)
            
            # Compensate flange coordinates to keep the tip stationary
            self.position["x"] = self._lock_needle_tip_start["x"] - needle_length * vx
            self.position["y"] = self._lock_needle_tip_start["y"] - needle_length * vy
            self.position["z"] = self._lock_needle_tip_start["z"] - needle_length * vz
            
            time.sleep(interval)
            
        self._tracker_running = False

    def stop_locked(self, needle_length=50.0):
        # Stop the physical motion
        self.stop()
        
        # Stop the tracker loop
        self._tracker_running = False
        
        if getattr(self, "_lock_needle_active", False):
            self._lock_needle_active = False
            self._active_jog_joint = None
            self._active_jog_dir = None
            
            # Apply post-jog alignment compensation
            self.apply_post_jog_compensation(
                self.position["x"] - self._lock_needle_start_pos["x"],
                self.position["y"] - self._lock_needle_start_pos["y"],
                self.position["z"] - self._lock_needle_start_pos["z"]
            )

    def apply_post_jog_compensation(self, dx, dy, dz):
        comp_thread = threading.Thread(
            target=self._post_jog_comp_loop,
            args=(dx, dy, dz),
            daemon=True
        )
        comp_thread.start()

    def _post_jog_comp_loop(self, dx, dy, dz):
        min_interval = getattr(self, "min_motion_interval", 0.2)
        
        # Compensate X
        steps_x = int(round(dx))
        if steps_x != 0:
            direction = "+" if steps_x > 0 else "-"
            for _ in range(abs(steps_x)):
                if getattr(self, "_cancel_move", False):
                    break
                self.jog_cartesian("X", direction)
                time.sleep(min_interval + 0.05)
                
        # Compensate Y
        steps_y = int(round(dy))
        if steps_y != 0:
            direction = "+" if steps_y > 0 else "-"
            for _ in range(abs(steps_y)):
                if getattr(self, "_cancel_move", False):
                    break
                self.jog_cartesian("Y", direction)
                time.sleep(min_interval + 0.05)
                
        # Compensate Z
        steps_z = int(round(dz))
        if steps_z != 0:
            direction = "+" if steps_z > 0 else "-"
            for _ in range(abs(steps_z)):
                if getattr(self, "_cancel_move", False):
                    break
                self.jog_cartesian("Z", direction)
                time.sleep(min_interval + 0.05)

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