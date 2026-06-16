import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # RCM Controller Node
    rcm_controller_node = Node(
        package='ar4_rcm_controller',
        executable='rcm_controller_node',
        name='rcm_controller_node',
        output='screen',
        parameters=[{
            'rcm_x': 0.35,
            'rcm_y': 0.0,
            'rcm_z': 0.35,
            'max_rcm_error': 0.0015
        }]
    )

    # Standard Mock Joint State Publisher to simulate the joint angles feedback in the loop
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{'source_list': ['/joint_trajectory']}]
    )

    # RViz2 Configuration
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(get_package_share_directory('ar4_rcm_controller'), 'config', 'rcm_viz.rviz')]
    )

    # Static Transform Publisher to define the fixed RCM point location visual marker
    rcm_marker_pub = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='rcm_static_tf_publisher',
        arguments=['0.35', '0.0', '0.35', '0', '0', '0', '1', 'world', 'rcm_point']
    )

    return LaunchDescription([
        rcm_controller_node,
        joint_state_publisher,
        rcm_marker_pub,
        rviz_node
    ])
