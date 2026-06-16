#!/usr/bin/env python3
"""Standalone AR4 RCM kinematics prototype.

This file mirrors the C++ controller math without requiring ROS 2. It is useful
for quick numerical checks before deploying the MoveIt-backed node.
"""

import math
import time
from dataclasses import dataclass

import numpy as np


@dataclass
class ToolCommand:
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0
    roll_rate: float = 0.0
    insertion_rate: float = 0.0


class AR4RcmPrototype:
    def __init__(self, rcm_point=None, tool_tip_offset=0.20):
        self.dh_params = [
            (0.0642, -math.pi / 2, 0.16977, 0.0),
            (0.305, 0.0, 0.0, -math.pi / 2),
            (0.0, -math.pi / 2, 0.0, 0.0),
            (0.0, math.pi / 2, 0.22263, 0.0),
            (0.0, -math.pi / 2, 0.0, 0.0),
            (0.0, 0.0, 0.03625, 0.0),
        ]
        self.tool_axis_local = np.array([0.0, 0.0, 1.0])
        self.rcm_point = np.array(rcm_point if rcm_point is not None else [0.35, 0.0, 0.35], dtype=float)
        self.tool_tip_offset = float(tool_tip_offset)

    @staticmethod
    def skew(vector):
        return np.array(
            [
                [0.0, -vector[2], vector[1]],
                [vector[2], 0.0, -vector[0]],
                [-vector[1], vector[0], 0.0],
            ]
        )

    @staticmethod
    def damped_pinv(matrix, damping=1e-3):
        u, singular_values, vt = np.linalg.svd(matrix, full_matrices=False)
        inverted = singular_values / (singular_values**2 + damping**2)
        return vt.T @ np.diag(inverted) @ u.T

    @staticmethod
    def dh_matrix(theta, a, alpha, d, theta_offset):
        theta = theta + theta_offset
        ct, st = math.cos(theta), math.sin(theta)
        ca, sa = math.cos(alpha), math.sin(alpha)
        return np.array(
            [
                [ct, -st * ca, st * sa, a * ct],
                [st, ct * ca, -ct * sa, a * st],
                [0.0, sa, ca, d],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )

    @staticmethod
    def pose_from_direction_roll(position, direction, roll_angle):
        z_axis = direction / np.linalg.norm(direction)
        reference = np.array([0.0, 0.0, 1.0])
        if abs(float(z_axis @ reference)) > 0.95:
            reference = np.array([1.0, 0.0, 0.0])

        x_axis = np.cross(reference, z_axis)
        x_axis /= np.linalg.norm(x_axis)
        y_axis = np.cross(z_axis, x_axis)
        y_axis /= np.linalg.norm(y_axis)

        k = z_axis
        kx = AR4RcmPrototype.skew(k)
        roll_matrix = np.eye(3) + math.sin(roll_angle) * kx + (1.0 - math.cos(roll_angle)) * (kx @ kx)
        rotation = np.column_stack((roll_matrix @ x_axis, roll_matrix @ y_axis, z_axis))

        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = position
        return transform

    def forward_kinematics(self, joints):
        transform = np.eye(4)
        transforms = [transform.copy()]
        for joint, params in zip(joints, self.dh_params):
            transform = transform @ self.dh_matrix(joint, *params)
            transforms.append(transform.copy())

        flange_position = transform[:3, 3]
        flange_rotation = transform[:3, :3]
        tool_direction = flange_rotation @ self.tool_axis_local
        tool_direction /= np.linalg.norm(tool_direction)
        return transform, transforms, flange_position, flange_rotation, tool_direction

    def geometric_jacobian(self, joints):
        _, transforms, flange_position, _, _ = self.forward_kinematics(joints)
        jacobian = np.zeros((6, 6))

        for index in range(6):
            axis = transforms[index][:3, 2]
            origin = transforms[index][:3, 3]
            jacobian[:3, index] = np.cross(axis, flange_position - origin)
            jacobian[3:, index] = axis

        return jacobian

    def compute_tool_tip_pose(self, direction, insertion_depth, roll_angle=0.0):
        direction = direction / np.linalg.norm(direction)
        tip_position = self.rcm_point + insertion_depth * direction
        flange_position = tip_position - self.tool_tip_offset * direction
        flange_pose = self.pose_from_direction_roll(flange_position, direction, roll_angle)
        return tip_position, flange_pose

    def compute_rcm_error(self, flange_position, tool_direction):
        flange_to_rcm = self.rcm_point - flange_position
        distance_along_tool = float(flange_to_rcm @ tool_direction)
        closest_point = flange_position + distance_along_tool * tool_direction
        return self.rcm_point - closest_point

    def compute_rcm_jacobian(self, joints, flange_position, tool_direction):
        geometric = self.geometric_jacobian(joints)
        j_pos = geometric[:3, :]
        j_rot = geometric[3:, :]
        distance_along_tool = float((self.rcm_point - flange_position) @ tool_direction)
        perpendicular = np.eye(3) - np.outer(tool_direction, tool_direction)
        return perpendicular @ j_pos - distance_along_tool * self.skew(tool_direction) @ j_rot

    def solve_rcm_step(self, joints, command, insertion_depth, kp_rcm=8.0, damping=1e-3):
        _, _, flange_position, _, tool_direction = self.forward_kinematics(joints)
        rcm_error = self.compute_rcm_error(flange_position, tool_direction)
        j_rcm = self.compute_rcm_jacobian(joints, flange_position, tool_direction)

        j_rcm_pinv = self.damped_pinv(j_rcm, damping)
        desired_rcm_velocity = kp_rcm * rcm_error
        qdot_rcm = j_rcm_pinv @ desired_rcm_velocity
        null_space = np.eye(6) - j_rcm_pinv @ j_rcm

        tool_frame = self.pose_from_direction_roll(np.zeros(3), tool_direction, 0.0)
        pitch_axis = tool_frame[:3, 0]
        yaw_axis = tool_frame[:3, 1]
        pivot_omega = command.pitch_rate * pitch_axis + command.yaw_rate * yaw_axis
        desired_tip_velocity = insertion_depth * np.cross(pivot_omega, tool_direction)
        desired_tip_velocity += command.insertion_rate * tool_direction

        geometric = self.geometric_jacobian(joints)
        j_tip = geometric[:3, :] - self.tool_tip_offset * self.skew(tool_direction) @ geometric[3:, :]
        qdot_tip = self.damped_pinv(j_tip @ null_space, damping) @ (
            desired_tip_velocity - j_tip @ qdot_rcm
        )
        qdot = qdot_rcm + null_space @ qdot_tip

        j_roll = tool_direction.reshape(1, 3) @ geometric[3:, :]
        projected_roll = j_roll @ null_space
        if np.linalg.norm(projected_roll) > 1e-9:
            current_roll_rate = float((j_roll @ qdot)[0])
            qdot += null_space @ (
                self.damped_pinv(projected_roll, damping)
                @ np.array([command.roll_rate - current_roll_rate])
            )

        qdot += j_rcm_pinv @ (desired_rcm_velocity - j_rcm @ qdot)
        return qdot, float(np.linalg.norm(rcm_error))


def run_simulation():
    controller = AR4RcmPrototype()
    joints = np.radians(np.array([0.0, -22.0, 18.0, 0.0, 30.0, 0.0]))
    insertion_depth = 0.10
    dt = 0.01
    max_error = 0.0

    def limit_joint_velocity(qdot, limit=0.7):
        maximum = float(np.max(np.abs(qdot)))
        return qdot * (limit / maximum) if maximum > limit else qdot

    print(f"RCM point: {controller.rcm_point}")
    print("Converging shaft to the RCM before teleoperation...")

    for step in range(600):
        qdot, error = controller.solve_rcm_step(joints, ToolCommand(), insertion_depth)
        joints += limit_joint_velocity(qdot) * dt
        if error < 5e-4:
            break

    print(f"Initial lock error: {error * 1000.0:.3f} mm")
    print("Running 100 Hz pivot/insertion prototype...")

    for step in range(400):
        elapsed = step * dt
        command = ToolCommand(
            pitch_rate=0.10 * math.sin(2.0 * math.pi * 0.25 * elapsed),
            yaw_rate=0.12 * math.cos(2.0 * math.pi * 0.20 * elapsed),
            roll_rate=0.25,
            insertion_rate=0.004 * math.sin(2.0 * math.pi * 0.15 * elapsed),
        )
        insertion_depth = float(np.clip(insertion_depth + command.insertion_rate * dt, 0.02, 0.24))
        qdot, error = controller.solve_rcm_step(joints, command, insertion_depth)
        joints += limit_joint_velocity(qdot) * dt
        max_error = max(max_error, error)

        if step % 50 == 0:
            _, _, _, _, direction = controller.forward_kinematics(joints)
            tip, _ = controller.compute_tool_tip_pose(direction, insertion_depth)
            print(
                f"{step:03d} error={error * 1000.0:7.3f} mm "
                f"insert={insertion_depth:.3f} m tip={np.round(tip, 3)}"
            )

        time.sleep(0.0)

    print(f"Max RCM error: {max_error * 1000.0:.3f} mm")


if __name__ == "__main__":
    run_simulation()
