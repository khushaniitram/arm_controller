import threading
import time

import serial
from serial.tools import list_ports

from .base_robot import BaseRobot


class TeensyRobot(BaseRobot):
    AXIS_MAP = {
        "X": 1,
        "Y": 2,
        "Z": 3,
        "R": 4,
        "P": 5,
        "W": 6,
    }

    def __init__(
        self,
        port=None,
        baudrate=9600,
        auto_detect=True,
        startup_delay=2.0,
        reconnect_interval=2.0,
        min_motion_interval=0.2,
    ):
        self.speed = 25
        self.position = {
            "x": 0,
            "y": 0,
            "z": 0,
            "j1": 0,
            "j2": 0,
            "j3": 0,
            "j4": 0,
            "j5": 0,
            "j6": 0,
        }

        self.preferred_port = port
        self.auto_detect = auto_detect
        self.baudrate = int(baudrate)
        self.startup_delay = float(startup_delay)
        self.reconnect_interval = float(reconnect_interval)
        self.min_motion_interval = float(min_motion_interval)

        self.serial = None
        self.connected_port = None
        self.mode = "Hardware Disconnected"
        self.last_error = None
        self.last_controller_message = None
        self.last_motion_error = None
        self._last_logged_connected = None

        self.running = True
        self._lock = threading.Lock()
        self._last_reconnect_attempt = 0.0
        self._last_motion_command_at = 0.0
        self._waiting_for_ack = False
        self._last_motion_sent_at = 0.0

        self._connect(force=True)

        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    @staticmethod
    def _list_ports():
        return list(list_ports.comports())

    @classmethod
    def detect_teensy_port(cls):
        ports = cls._list_ports()
        if not ports:
            return None

        keywords = ("teensy", "usb serial", "ch340", "arduino", "cp210")
        ranked = []
        for info in ports:
            haystack = " ".join(
                [
                    info.device or "",
                    info.description or "",
                    info.manufacturer or "",
                    info.hwid or "",
                ]
            ).lower()
            score = sum(1 for kw in keywords if kw in haystack)
            ranked.append((score, info))

        ranked.sort(key=lambda item: item[0], reverse=True)
        best_score, best_port = ranked[0]
        if best_score > 0:
            print(f"Auto-detected robot serial port: {best_port.device} ({best_port.description})")
            return best_port.device
        return None

    @classmethod
    def available_ports_text(cls):
        ports = cls._list_ports()
        if not ports:
            return "none"
        return ", ".join(f"{p.device} ({p.description})" for p in ports)

    def _mark_disconnected(self, reason=None):
        if reason:
            self.last_error = reason
            if self._last_logged_connected is not False:
                print(f"[ROBOT] disconnected: {reason}")
                self._last_logged_connected = False
        else:
            self._last_logged_connected = False
        self.mode = "Hardware Disconnected"

        if self.serial is not None:
            try:
                if self.serial.is_open:
                    self.serial.close()
            except Exception:
                pass
        self.serial = None
        self.connected_port = None

    def _candidate_ports(self):
        candidates = []
        if self.preferred_port:
            candidates.append(self.preferred_port)

        if self.auto_detect:
            detected = self.detect_teensy_port()
            if detected:
                candidates.append(detected)

        # Keep order, remove duplicates.
        unique = []
        seen = set()
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        return unique

    def _connect(self, force=False):
        if self.serial and self.serial.is_open:
            if self._last_logged_connected is not True:
                print(f"[ROBOT] connected on {self.connected_port}")
                self._last_logged_connected = True
            return True

        now = time.time()
        if not force and (now - self._last_reconnect_attempt) < self.reconnect_interval:
            return False
        self._last_reconnect_attempt = now

        candidates = self._candidate_ports()
        if not candidates:
            self.last_error = "No configured/detected serial port"
            self.mode = "Hardware Disconnected"
            if self._last_logged_connected is not False:
                print("[ROBOT] no serial candidates.")
                self._last_logged_connected = False
            return False

        for candidate in candidates:
            try:
                if self._last_logged_connected is not False:
                    print(f"[ROBOT] connecting on {candidate} @ {self.baudrate}...")
                self.serial = serial.Serial(
                    candidate,
                    self.baudrate,
                    timeout=1,
                    write_timeout=1,
                )
                # Teensy often resets on open.
                time.sleep(self.startup_delay)
                self.connected_port = candidate
                self.mode = "Hardware Connected"
                self.last_error = None
                print(f"[ROBOT] connected on {candidate}")
                self._last_logged_connected = True
                return True
            except Exception as exc:
                msg = str(exc)
                if "Access is denied" in msg:
                    msg = (
                        f"{msg}. Port is busy. Close Arduino/Teensy serial tools "
                        "or another backend using this COM port."
                    )
                self.last_error = msg
                if self._last_logged_connected is not False:
                    print(f"[ROBOT] connect failed on {candidate}: {msg}")
                self._mark_disconnected()

        if self._last_logged_connected is not False:
            print("[ROBOT] reconnect failed.")
            self._last_logged_connected = False
        return False

    def _ensure_connected(self):
        if self.serial and self.serial.is_open:
            if self.mode != "Hardware Connected":
                self.mode = "Hardware Connected"
            return True
        return self._connect()

    @staticmethod
    def _is_motion_command(cmd):
        return cmd.startswith("LJV") or cmd.startswith("LCV")

    def _send_command(self, cmd):
        if not self._ensure_connected():
            print(f"Command skipped (serial disconnected): {cmd}")
            return False

        now = time.time()
        if self._is_motion_command(cmd):
            # If we are waiting for an ACK and it hasn't timed out (1.0 sec), skip the command
            if self._waiting_for_ack and (now - self._last_motion_sent_at) < 1.0:
                return False

            if (now - self._last_motion_command_at) < self.min_motion_interval:
                return False
            self._last_motion_command_at = now
            self._waiting_for_ack = True
            self._last_motion_sent_at = now
        elif cmd == "SS":
            # Stop command immediately clears the waiting state and goes through
            self._waiting_for_ack = False

        try:
            payload = f"{cmd}\n".encode("utf-8")
            with self._lock:
                self.serial.write(payload)
                self.serial.flush()
            print(f"[ROBOT] -> {cmd}")
            if cmd == "SS":
                self.last_motion_error = None
            return True
        except Exception as exc:
            self._mark_disconnected(str(exc))
            print(f"Command skipped (serial disconnected): {cmd}")
            return False

    def _read_loop(self):
        while self.running:
            if not self._ensure_connected():
                time.sleep(0.25)
                continue

            try:
                if self.serial.in_waiting > 0:
                    line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.last_controller_message = line
                        if line.startswith("EL"):
                            self.last_motion_error = f"Motion limit reached: {line}"
                            self._waiting_for_ack = False
                        elif line.startswith("ER"):
                            self.last_motion_error = f"Controller rejected motion command: {line}"
                            self._waiting_for_ack = False
                        elif line.startswith("A"):
                            self.last_motion_error = None
                            self._waiting_for_ack = False
                        print(f"[ROBOT] <- {line}")
            except Exception as exc:
                self._mark_disconnected(str(exc))

            time.sleep(0.01)

    def jog_joint(self, joint, direction):
        if direction not in {"+", "-"}:
            raise ValueError(f"Invalid joint direction: {direction}")
        if joint < 1 or joint > 6:
            raise ValueError(f"Invalid joint index: {joint}")

        move_dir = "1" if direction == "+" else "0"
        cmd = f"LJV{joint}{move_dir}Sp{self.speed}Ac15Dc15Rm80WLm000000"
        if self._send_command(cmd):
            amount = 1 if direction == "+" else -1
            self.position[f"j{joint}"] += amount

    def jog_cartesian(self, axis, direction):
        if direction not in {"+", "-"}:
            raise ValueError(f"Invalid cartesian direction: {direction}")

        axis_upper = axis.upper()
        if axis_upper not in self.AXIS_MAP:
            raise ValueError(f"Invalid axis: {axis}")

        axis_number = self.AXIS_MAP[axis_upper]
        move_dir = "1" if direction == "+" else "0"
        cmd = f"LCV{axis_number}{move_dir}Sp{self.speed}Ac15Dc15Rm80WFLm000000"
        if self._send_command(cmd):
            amount = 1 if direction == "+" else -1
            axis_key = axis_upper.lower()
            if axis_key in self.position:
                self.position[axis_key] += amount

    def stop(self):
        self.cancel_move_to()
        self._send_command("SS")

    def set_speed(self, speed):
        clamped = max(1, min(100, int(speed)))
        self.speed = clamped
        print(f"[ROBOT] speed set to {clamped}")

    def read_feedback(self):
        feedback = self.position.copy()
        feedback["mode"] = self.mode
        feedback["speed"] = self.speed
        feedback["connected"] = bool(self.serial and self.serial.is_open)
        feedback["port"] = self.connected_port
        feedback["error"] = self.last_error
        feedback["controller_message"] = self.last_controller_message
        feedback["motion_error"] = self.last_motion_error
        feedback["moving_to_coords"] = self.is_moving_to_coords()
        return feedback

    def close(self):
        self.cancel_move_to()
        self.running = False
        self._mark_disconnected()
