cmake_minimum_required(VERSION 3.8)
project(ar4_rcm_controller)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(moveit_core REQUIRED)
find_package(moveit_ros_planning REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(trajectory_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)

add_library(rcm_kinematics
  src/rcm_kinematics.cpp
)
target_compile_features(rcm_kinematics PUBLIC cxx_std_17)
target_include_directories(rcm_kinematics PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(rcm_kinematics
  Eigen3::Eigen
)
ament_target_dependencies(rcm_kinematics
  moveit_core
)

add_executable(rcm_controller_node
  src/rcm_controller_node.cpp
)
target_compile_features(rcm_controller_node PUBLIC cxx_std_17)
target_link_libraries(rcm_controller_node
  rcm_kinematics
  Eigen3::Eigen
)
ament_target_dependencies(rcm_controller_node
  geometry_msgs
  moveit_core
  moveit_ros_planning
  rclcpp
  sensor_msgs
  std_msgs
  tf2
  tf2_geometry_msgs
  tf2_ros
  trajectory_msgs
  visualization_msgs
)

install(
  DIRECTORY include/
  DESTINATION include
)

install(TARGETS
  rcm_kinematics
  EXPORT export_rcm_kinematics
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(TARGETS
  rcm_controller_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch config docs
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  ar4_rcm_controller/rcm_kinematics_prototype.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_export_targets(export_rcm_kinematics HAS_LIBRARY_TARGET)
ament_export_dependencies(moveit_core)
ament_package()
