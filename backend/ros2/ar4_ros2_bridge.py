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
    print("This script is written as a template and driver bridge to be run within your ROS 2 workspace.")
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
                def info(self, msg): print(msg)
                def warn(self, msg): print(msg)
                def error(self, msg): print(msg)
            return Logger()
        def get_clock(self):
            class Clock:
                def now(self):
                    class Time:
                        def to_msg(self): return None
                    return Time()
            return Clock()

class AR4Ros2Bridge(Node):
    def __init__(self, ws_url="ws://localhost:8000/ws"):
        super().__init__("ar4_ros2_bridge")
        self.ws_url = ws_url
        self.connected = False
        self.ws = None
        self.loop = None
        self.current_joints = [0.0] * 6 # in degrees

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
                        if "position" in data:
                            pos = data["position"]
                            node.current_joints = [
                                pos.get("j1", 0.0),
                                pos.get("j2", 0.0),
                                pos.get("j3", 0.0),
                                pos.get("j4", 0.0),
                                pos.get("j5", 0.0),
                                pos.get("j6", 0.0)
                            ]
                            node.publish_joint_states()
                    except Exception as e:
                        node.get_logger().error(f"Error parsing message: {e}")
        except Exception as e:
            node.connected = False
            node.ws = None
            node.get_logger().warn(f"WebSocket disconnected or failed: {e}. Reconnecting in 2s...")
            await asyncio.sleep(2.0)

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

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    if "rclpy" not in sys.modules:
        print("[ERROR] Please source your ROS 2 environment (e.g. source /opt/ros/humble/setup.bash) before running this script.")
        sys.exit(1)
    main()
