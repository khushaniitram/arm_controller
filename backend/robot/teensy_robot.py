import serial
import threading
import time
from .base_robot import BaseRobot

class TeensyRobot(BaseRobot):
    def __init__(self, port="COM4", baudrate=115200):
        self.speed = 25
        self.position = {
            "x": 0, "y": 0, "z": 0,
            "j1": 0, "j2": 0, "j3": 0, "j4": 0, "j5": 0, "j6": 0
        }
        self.mode = "Hardware Connected"
        self.serial = None
        self.running = True
        
        try:
            print(f"\nAttempting to connect to Teensy on {port}...")
            self.serial = serial.Serial(port, baudrate, timeout=1)
            print("✓ Teensy Robot Connected")
            
            # Start background thread to read feedback
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
        except Exception as e:
            print(f"✗ Failed to connect to Teensy: {e}")
            self.mode = "Hardware Disconnected"

    def _send_command(self, cmd):
        if self.serial and self.serial.is_open:
            try:
                self.serial.write(f"{cmd}\n".encode('utf-8'))
            except Exception as e:
                print(f"Serial write error: {e}")
                self.mode = "Hardware Disconnected"

    def _read_loop(self):
        while self.running:
            if self.serial and self.serial.is_open:
                try:
                    if self.serial.in_waiting > 0:
                        line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                        # Here you can parse incoming feedback from Teensy if it sends coordinates back
                        # e.g. "POS X:10 Y:20 Z:30 J1:5 J2:10..."
                        pass
                except Exception as e:
                    print(f"Serial read error: {e}")
                    self.mode = "Hardware Disconnected"
            time.sleep(0.01)

    def jog_joint(self, joint, direction):
        cmd = f"J{joint}{direction}"
        self._send_command(cmd)
        
        # Simulate local update for UI responsiveness (until exact hardware feedback protocol is set)
        amount = 1 if direction == "+" else -1
        self.position[f"j{joint}"] += amount

    def jog_cartesian(self, axis, direction):
        axis_upper = axis.upper()
        cmd = f"{axis_upper}{direction}"
        self._send_command(cmd)
        
        # Simulate local update
        amount = 1 if direction == "+" else -1
        self.position[axis.lower()] += amount

    def stop(self):
        self._send_command("STOP")

    def set_speed(self, speed):
        self.speed = speed
        self._send_command(f"SPEED:{speed}")

    def read_feedback(self):
        feedback = self.position.copy()
        feedback["mode"] = self.mode
        return feedback
        
    def close(self):
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
