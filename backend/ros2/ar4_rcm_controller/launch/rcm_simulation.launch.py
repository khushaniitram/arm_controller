import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = get_package_share_directory("ar4_rcm_controller")
    params_file = LaunchConfiguration("params_file")
    use_rviz = LaunchConfiguration("use_rviz")
    use_joint_state_publisher = LaunchConfiguration("use_joint_state_publisher")
    robot_description_package = LaunchConfiguration("robot_description_package")
    robot_description_file = LaunchConfiguration("robot_description_file")

    robot_description_content = Command(
        [
            "xacro ",
            PathJoinSubstitution(
                [
                    FindPackageShare(robot_description_package),
                    robot_description_file,
                ]
            ),
        ]
    )

    robot_description = {"robot_description": robot_description_content}

    rcm_controller_node = Node(
        package="ar4_rcm_controller",
        executable="rcm_controller_node",
        name="rcm_controller_node",
        output="screen",
        parameters=[params_file, robot_description],
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[robot_description],
    )

    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        condition=IfCondition(use_joint_state_publisher),
        parameters=[{"source_list": ["/joint_trajectory"]}],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        condition=IfCondition(use_rviz),
        arguments=[
            "-d",
            os.path.join(package_share, "config", "rcm_viz.rviz"),
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value=os.path.join(package_share, "config", "rcm_params.yaml"),
                description="RCM controller parameter YAML file.",
            ),
            DeclareLaunchArgument(
                "robot_description_package",
                default_value="ar4_moveit_config",
                description="Package containing the AR4 URDF/Xacro.",
            ),
            DeclareLaunchArgument(
                "robot_description_file",
                default_value="config/ar4.urdf.xacro",
                description="URDF/Xacro path inside robot_description_package.",
            ),
            DeclareLaunchArgument(
                "use_joint_state_publisher",
                default_value="true",
                description="Use a mock joint_state_publisher for simulation.",
            ),
            DeclareLaunchArgument(
                "use_rviz",
                default_value="true",
                description="Launch RViz with the RCM visualization config.",
            ),
            robot_state_publisher,
            joint_state_publisher,
            rcm_controller_node,
            rviz_node,
        ]
    )
