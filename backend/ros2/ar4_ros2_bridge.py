#!/usr/bin/env python3
import sys
import math
import json
import asyncio
import threading
import websockets

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Header
    from trajectory_msgs.msg import JointTrajectory
except ImportError:
    print("[WARN] ROS 2 (rclpy) is not installed or sourced in this environment.")
    print("Running in MOCK ROS 2 MODE for simulation and local web server testing.")
    # Fallbacks for syntax check
    class JointState: pass
    class Header: pass
    class JointTrajectory: pass
    class Node:
        def __init__(self, name): pass
        def create_publisher(self, type, topic, qos): return None
        def create_subscription(self, type, topic, cb, qos): return None
        def get_logger(self):
            class Logger:
                def info(self, msg): print(f"[INFO] {msg}")
                def warn(self, msg): print(f"[WARN] {msg}")
                def error(self, msg): print(f"[ERROR] {msg}")
            return Logger()
        def get_clock(self):
            class Clock:
                def now(self):
                    class Time:
                        def to_msg(self): return None
                    return Time()
            return Clock()
        def destroy_node(self):
            pass

    class MockRclpy:
        @staticmethod
        def ok():
            return True
        @staticmethod
        def init(args=None):
            print("[MOCK] Initializing Mock rclpy...")
        @staticmethod
        def shutdown():
            print("[MOCK] Shutting down Mock rclpy...")
        @staticmethod
        def spin_once(node, timeout_sec=0.0):
            pass
    rclpy = MockRclpy

class AR4Ros2Bridge(Node):
    def __init__(self, ws_url="ws://localhost:8000/ws"):
        super().__init__("ar4_ros2_bridge")
        self.ws_url = ws_url
        self.connected = False
        self.ws = None
        self.loop = None
        self.current_joints = [0.0] * 6 # in degrees
        self.have_feedback = False

        # JointState Publisher (Standard for robot_state_publisher and MoveIt 2)
        self.joint_state_pub = self.create_publisher(JointState, "/joint_states", 10)

        # Joint trajectory subscription (To receive goals from MoveIt 2 / controllers)
        self.trajectory_sub = self.create_subscription(
            JointTrajectory,
            "/joint_trajectory",
            self.trajectory_callback,
            10
        )

    def publish_joint_states(self):
        msg = JointState()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        
        # AR4 joint names matching URDF
        msg.name = [
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6"
        ]
        
        # ROS 2 MoveIt 2 expects radians
        msg.position = [math.radians(deg) for deg in self.current_joints]
        self.joint_state_pub.publish(msg)

    def trajectory_callback(self, msg: JointTrajectory):
        if not self.connected or not self.ws or not self.loop:
            self.get_logger().warn("Cannot command robot: WebSocket not connected.")
            return

        if not self.have_feedback:
            self.get_logger().warn("Cannot command robot: waiting for initial joint feedback.")
            return

        if not msg.points:
            return

        # Fetch the last trajectory point target
        target_point = msg.points[-1]
        target_positions = target_point.positions # in radians

        any_moving = False
        # Command joints based on target difference
        for i, target_rad in enumerate(target_positions):
            if i >= 6:
                break
            target_deg = math.degrees(target_rad)
            current_deg = self.current_joints[i]
            diff = target_deg - current_deg

            # If there's a difference > 0.5 degrees, command a jog step
            if abs(diff) > 0.5:
                any_moving = True
                direction = "+" if diff > 0 else "-"
                cmd = {
                    "command": "joint",
                    "joint": i + 1,
                    "direction": direction
                }
                # Send the jog message to the websocket through the running event loop
                asyncio.run_coroutine_threadsafe(
                    self.ws.send(json.dumps(cmd)),
                    self.loop
                )

        if not any_moving:
            cmd = {
                "command": "stop"
            }
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(cmd)),
                self.loop
            )

async def receive_websocket(node, ws_url):
    while rclpy.ok():
        try:
            node.get_logger().info(f"Connecting to backend WebSocket at {ws_url}...")
            async with websockets.connect(ws_url) as ws:
                node.ws = ws
                node.connected = True
                node.get_logger().info("Successfully connected to AR4 Backend WebSocket!")
                
                async for message in ws:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "feedback":
                            pos = data.get("data", {})
                        elif "position" in data:
                            pos = data["position"]
                        else:
                            pos = None

                        if pos:
                            if pos.get("feedback_ready") is False and pos.get("mode") != "Simulation Mode":
                                continue
                            node.current_joints = [
                                pos.get("j1", 0.0),
                                pos.get("j2", 0.0),
                                pos.get("j3", 0.0),
                                pos.get("j4", 0.0),
                                pos.get("j5", 0.0),
                                pos.get("j6", 0.0)
                            ]
                            node.have_feedback = True
                            node.publish_joint_states()
                    except Exception as e:
                        node.get_logger().error(f"Error parsing message: {e}")
        except Exception as e:
            node.connected = False
            node.ws = None
            node.get_logger().warn(f"WebSocket disconnected or failed: {e}. Reconnecting in 2s...")
            await asyncio.sleep(2.0)

async def mock_trajectory_commands(node):
    import time
    await asyncio.sleep(5.0)
    while True:
        if node.connected:
            node.get_logger().info("Generating mock joint trajectory movement...")
            class MockPoint:
                def __init__(self, positions):
                    self.positions = positions
            class MockTrajectory:
                def __init__(self, positions):
                    self.points = [MockPoint(positions)]
            
            # Target a slight offset
            offset = 1.0 if (int(time.time()) // 10) % 2 == 0 else -1.0
            target_positions = [math.radians(deg + offset) for deg in node.current_joints]
            msg = MockTrajectory(target_positions)
            node.trajectory_callback(msg)
        await asyncio.sleep(10.0)

async def spin_node_async(node):
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.01)
        await asyncio.sleep(0.01)

def main(args=None):
    rclpy.init(args=args)
    node = AR4Ros2Bridge()
    
    # Create the event loop
    loop = asyncio.get_event_loop()
    node.loop = loop

    # Schedule tasks
    loop.create_task(receive_websocket(node, node.ws_url))
    loop.create_task(spin_node_async(node))
    
    # Check if we are running in mock mode
    if rclpy.__name__ == "MockRclpy" or (hasattr(rclpy, "__name__") and rclpy.__name__ == "MockRclpy") or "MockRclpy" in str(rclpy):
        loop.create_task(mock_trajectory_commands(node))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
