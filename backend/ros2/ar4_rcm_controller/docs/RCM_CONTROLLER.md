# AR4 Remote Center of Motion Controller

This package implements a velocity-level Remote Center of Motion (RCM) controller for a 6-DOF AR4 arm modeled in URDF and loaded through MoveIt 2. The surgical entry point is fixed in the base frame and the instrument shaft is servoed so the shaft line continues to pass through that entry point while the operator commands pitch, yaw, roll, and insertion.

## Coordinate Definitions

- `p_r`: fixed RCM point in the base frame.
- `p_f`: flange or tool frame origin from forward kinematics.
- `u`: unit shaft direction in the base frame.
- `s`: insertion depth from RCM to tool tip.
- `l_t`: fixed flange-to-tip distance along `u`.
- `q`: six AR4 joint angles.
- `J_v(q)`, `J_w(q)`: translational and angular geometric Jacobians at the flange.

The shaft line is:

```text
L(a) = p_f + a u
```

The closest point on the shaft to the RCM is:

```text
d = (p_r - p_f)^T u
p_c = p_f + d u
```

The RCM error is:

```text
e_rcm = p_r - p_c
      = (I - u u^T)(p_r - p_f)
```

The controller rejects motion when `||e_rcm|| > max_rcm_error`. The default is `0.001 m` (1 mm).

## Forward Kinematics

MoveIt supplies the URDF-derived forward kinematics:

```text
T_0_f(q) = [ R_0_f(q)  p_f(q) ]
           [    0          1   ]

u(q) = R_0_f(q) u_f
```

where `u_f` is the configured local shaft axis, normally `[0, 0, 1]`.

Given RCM, direction, and insertion depth, the commanded tip pose is:

```text
p_tip = p_r + s u
R_tip = basis_from_direction_and_roll(u, phi)
T_tip = [ R_tip  p_tip ]
        [   0      1   ]
```

The corresponding flange target for a tool length `l_t` is:

```text
p_f,target = p_tip - l_t u
```

## RCM Jacobian

The closest shaft point velocity is:

```text
dot(p_c) = (I - u u^T) dot(p_f) + d dot(u)
dot(u) = omega x u = -[u]x omega
```

Therefore the line-point Jacobian used to keep the RCM fixed is:

```text
J_rcm = (I - u u^T) J_v - d [u]x J_w
dot(p_c) = J_rcm dot(q)
```

The controller commands the line point toward the fixed RCM:

```text
dot(q)_rcm = J_rcm# (K_rcm e_rcm)
```

where `#` is a damped least-squares pseudo-inverse.

## Pitch, Yaw, Roll, and Insertion

Pitch and yaw are operator angular rates around axes perpendicular to the shaft. Roll is angular velocity around `u`. Insertion is linear velocity along `u`.

```text
omega_pivot = pitch_rate x_tool + yaw_rate y_tool
dot(p_tip) = s (omega_pivot x u) + insertion_rate u
```

The secondary task is projected into the RCM null space:

```text
N = I - J_rcm# J_rcm
dot(q) = dot(q)_rcm + N (J_tip N)# (dot(p_tip) - J_tip dot(q)_rcm)
```

Roll is applied as another projected task:

```text
J_roll = u^T J_w
dot(q) += N (J_roll N)# (roll_rate - J_roll dot(q))
```

## ROS 2 Interfaces

- Subscribes: `/joint_states` (`sensor_msgs/JointState`)
- Subscribes: `/rcm/cmd_vel` (`geometry_msgs/Twist`)
  - `angular.x`: pitch rate, rad/s
  - `angular.y`: yaw rate, rad/s
  - `angular.z`: roll rate, rad/s
  - `linear.z`: insertion/retraction rate, m/s
- Publishes: `/joint_trajectory` (`trajectory_msgs/JointTrajectory`)
- Publishes: `/rcm/tool_pose` (`geometry_msgs/PoseStamped`)
- Publishes: `/rcm/error_mm` (`std_msgs/Float64`)
- Publishes: `/rcm/markers` (`visualization_msgs/MarkerArray`)

## Package Structure

```text
ar4_rcm_controller/
  include/ar4_rcm_controller/rcm_kinematics.hpp
  src/rcm_kinematics.cpp
  src/rcm_controller_node.cpp
  ar4_rcm_controller/rcm_kinematics_prototype.py
  config/rcm_params.yaml
  config/rcm_viz.rviz
  launch/rcm_simulation.launch.py
  docs/RCM_CONTROLLER.md
```

## Simulation First

1. Put this package in a ROS 2 workspace with the AR4 URDF/MoveIt config.
2. Build:

```bash
colcon build --packages-select ar4_rcm_controller
source install/setup.bash
```

3. Launch simulation/RViz:

```bash
ros2 launch ar4_rcm_controller rcm_simulation.launch.py \
  robot_description_package:=ar4_moveit_config \
  robot_description_file:=config/ar4.urdf.xacro
```

4. Send a gentle insertion command:

```bash
ros2 topic pub /rcm/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {z: 0.005}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

5. Watch `/rcm/error_mm`. Do not deploy to hardware until simulated RCM error stays below 1 mm and all joint directions match the physical robot.

## Hardware Deployment Checklist

- Confirm AR4 URDF joint names match the Teensy/backend joint names.
- Confirm the configured `tool_axis` matches the physical shaft axis.
- Confirm `tool_tip_offset`, insertion limits, and RCM point are measured in meters.
- Start the backend and wait until `feedback_ready=true`; motion commands are rejected until real controller feedback arrives.
- Verify camera `/camera/status` reports `connected=true` and `has_frame=true`.
- Start with low `max_joint_velocity`, `max_pitch_rate`, and `max_insertion_rate`.
- Keep hardware E-stop available during first validation.
