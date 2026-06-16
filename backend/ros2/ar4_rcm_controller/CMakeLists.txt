cmake_minimum_required(VERSION 3.8)
project(ar4_rcm_controller)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -std=c++17)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(moveit_core REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

include_directories(include)

# Create library for RCM Kinematics
add_library(rcm_kinematics
  src/rcm_kinematics.cpp
)
target_link_libraries(rcm_kinematics
  moveit_core::moveit_core
  moveit_ros_planning_interface::moveit_ros_planning_interface
)

# Create Node
add_executable(rcm_controller_node
  src/rcm_controller_node.cpp
)
target_link_libraries(rcm_controller_node
  rcm_kinematics
  rclcpp::rclcpp
  geometry_msgs::geometry_msgs
  tf2::tf2
  tf2_ros::tf2_ros
)

# Install
install(TARGETS
  rcm_kinematics
  rcm_controller_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
