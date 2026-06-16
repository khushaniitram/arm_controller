#include "ar4_rcm_controller/rcm_kinematics.hpp"

#include <Eigen/Dense>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <memory>
#include <mutex>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <std_msgs/msg/float64.hpp>
#include <string>
#include <trajectory_msgs/msg/joint_trajectory.hpp>
#include <trajectory_msgs/msg/joint_trajectory_point.hpp>
#include <unordered_set>
#include <utility>
#include <visualization_msgs/msg/marker.hpp>
#include <visualization_msgs/msg/marker_array.hpp>

#include <moveit/robot_model_loader/robot_model_loader.h>
#include <moveit/robot_state/robot_state.h>

using namespace std::chrono_literals;

namespace {

geometry_msgs::msg::Point toPoint(const Eigen::Vector3d& vector) {
  geometry_msgs::msg::Point point;
  point.x = vector.x();
  point.y = vector.y();
  point.z = vector.z();
  return point;
}

geometry_msgs::msg::Pose toPose(const Eigen::Isometry3d& transform) {
  geometry_msgs::msg::Pose pose;
  pose.position = toPoint(transform.translation());
  const Eigen::Quaterniond quaternion(transform.rotation());
  pose.orientation.x = quaternion.x();
  pose.orientation.y = quaternion.y();
  pose.orientation.z = quaternion.z();
  pose.orientation.w = quaternion.w();
  return pose;
}

visualization_msgs::msg::Marker baseMarker(
    const std::string& frame_id,
    const rclcpp::Time& stamp,
    const std::string& ns,
    int id,
    int type) {
  visualization_msgs::msg::Marker marker;
  marker.header.frame_id = frame_id;
  marker.header.stamp = stamp;
  marker.ns = ns;
  marker.id = id;
  marker.type = type;
  marker.action = visualization_msgs::msg::Marker::ADD;
  marker.pose.orientation.w = 1.0;
  marker.lifetime = rclcpp::Duration::from_seconds(0.2);
  return marker;
}

} // namespace

class RcmControllerNode : public rclcpp::Node {
public:
  RcmControllerNode() : Node("rcm_controller_node") {
    declareParameters();
  }

  bool initialize() {
    loadParameters();

    robot_model_loader::RobotModelLoader robot_model_loader(
        shared_from_this(), "robot_description");
    robot_model_ = robot_model_loader.getModel();
    if (!robot_model_) {
      RCLCPP_FATAL(get_logger(), "Failed to load MoveIt robot model from robot_description");
      return false;
    }

    robot_state_ = std::make_shared<moveit::core::RobotState>(robot_model_);
    robot_state_->setToDefaultValues();
    robot_state_->update();

    try {
      rcm_kinematics_ = std::make_unique<ar4_rcm::RcmKinematics>(
          robot_model_, planning_group_, ee_link_);
      rcm_kinematics_->setRcmPoint(rcm_point_);
      rcm_kinematics_->setToolAxisLocal(tool_axis_local_);
      rcm_kinematics_->setToolTipOffset(tool_tip_offset_);
    } catch (const std::exception& exception) {
      RCLCPP_FATAL(get_logger(), "RCM initialization failed: %s", exception.what());
      return false;
    }

    joint_names_ = rcm_kinematics_->jointModelGroup()->getVariableNames();
    joint_name_set_ = std::unordered_set<std::string>(joint_names_.begin(), joint_names_.end());

    current_direction_ = rcm_kinematics_->currentToolDirection(*robot_state_);
    last_command_time_ = now();

    joint_state_sub_ = create_subscription<sensor_msgs::msg::JointState>(
        joint_state_topic_, rclcpp::SensorDataQoS(),
        std::bind(&RcmControllerNode::jointStateCallback, this, std::placeholders::_1));

    cmd_vel_sub_ = create_subscription<geometry_msgs::msg::Twist>(
        command_topic_, 10,
        std::bind(&RcmControllerNode::cmdVelCallback, this, std::placeholders::_1));

    joint_pub_ = create_publisher<trajectory_msgs::msg::JointTrajectory>(
        trajectory_topic_, 10);
    tool_pose_pub_ = create_publisher<geometry_msgs::msg::PoseStamped>(
        "/rcm/tool_pose", 10);
    error_pub_ = create_publisher<std_msgs::msg::Float64>(
        "/rcm/error_mm", 10);
    marker_pub_ = create_publisher<visualization_msgs::msg::MarkerArray>(
        "/rcm/markers", 10);

    const auto period = std::chrono::duration<double>(1.0 / control_rate_hz_);
    timer_ = create_wall_timer(
        std::chrono::duration_cast<std::chrono::nanoseconds>(period),
        std::bind(&RcmControllerNode::controlLoop, this));

    RCLCPP_INFO(
        get_logger(),
        "RCM controller ready: point=(%.3f, %.3f, %.3f), insertion=%.3f m, rate=%.1f Hz",
        rcm_point_.x(), rcm_point_.y(), rcm_point_.z(), insertion_depth_, control_rate_hz_);
    return true;
  }

private:
  void declareParameters() {
    declare_parameter<double>("rcm_x", 0.35);
    declare_parameter<double>("rcm_y", 0.0);
    declare_parameter<double>("rcm_z", 0.35);
    declare_parameter<std::string>("base_frame", "world");
    declare_parameter<std::string>("planning_group", "arm");
    declare_parameter<std::string>("ee_link", "link_6");
    declare_parameter<std::vector<double>>("tool_axis", {0.0, 0.0, 1.0});
    declare_parameter<double>("tool_tip_offset", 0.20);
    declare_parameter<double>("initial_insertion_depth", 0.10);
    declare_parameter<double>("min_insertion_depth", 0.02);
    declare_parameter<double>("max_insertion_depth", 0.24);
    declare_parameter<double>("max_rcm_error", 0.001);
    declare_parameter<double>("control_rate", 100.0);
    declare_parameter<double>("kp_rcm", 8.0);
    declare_parameter<double>("damping", 1e-3);
    declare_parameter<double>("max_joint_velocity", 0.7);
    declare_parameter<double>("max_pitch_rate", 0.35);
    declare_parameter<double>("max_yaw_rate", 0.35);
    declare_parameter<double>("max_roll_rate", 0.8);
    declare_parameter<double>("max_insertion_rate", 0.03);
    declare_parameter<double>("command_timeout", 0.25);
    declare_parameter<std::string>("joint_state_topic", "/joint_states");
    declare_parameter<std::string>("command_topic", "/rcm/cmd_vel");
    declare_parameter<std::string>("trajectory_topic", "/joint_trajectory");
  }

  void loadParameters() {
    rcm_point_ << get_parameter("rcm_x").as_double(),
                  get_parameter("rcm_y").as_double(),
                  get_parameter("rcm_z").as_double();
    base_frame_ = get_parameter("base_frame").as_string();
    planning_group_ = get_parameter("planning_group").as_string();
    ee_link_ = get_parameter("ee_link").as_string();

    const auto axis = get_parameter("tool_axis").as_double_array();
    if (axis.size() == 3) {
      tool_axis_local_ << axis[0], axis[1], axis[2];
    }

    tool_tip_offset_ = get_parameter("tool_tip_offset").as_double();
    insertion_depth_ = get_parameter("initial_insertion_depth").as_double();
    min_insertion_depth_ = get_parameter("min_insertion_depth").as_double();
    max_insertion_depth_ = get_parameter("max_insertion_depth").as_double();
    max_rcm_error_ = get_parameter("max_rcm_error").as_double();
    control_rate_hz_ = std::clamp(get_parameter("control_rate").as_double(), 50.0, 100.0);
    kp_rcm_ = get_parameter("kp_rcm").as_double();
    damping_ = get_parameter("damping").as_double();
    max_joint_velocity_ = get_parameter("max_joint_velocity").as_double();
    max_pitch_rate_ = get_parameter("max_pitch_rate").as_double();
    max_yaw_rate_ = get_parameter("max_yaw_rate").as_double();
    max_roll_rate_ = get_parameter("max_roll_rate").as_double();
    max_insertion_rate_ = get_parameter("max_insertion_rate").as_double();
    command_timeout_ = get_parameter("command_timeout").as_double();
    joint_state_topic_ = get_parameter("joint_state_topic").as_string();
    command_topic_ = get_parameter("command_topic").as_string();
    trajectory_topic_ = get_parameter("trajectory_topic").as_string();

    if (tool_axis_local_.norm() < 1e-9) {
      tool_axis_local_ = Eigen::Vector3d::UnitZ();
    }
    tool_axis_local_.normalize();
    insertion_depth_ = std::clamp(insertion_depth_, min_insertion_depth_, max_insertion_depth_);
  }

  void jointStateCallback(const sensor_msgs::msg::JointState::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    const std::size_t count = std::min(msg->name.size(), msg->position.size());
    bool updated = false;

    for (std::size_t index = 0; index < count; ++index) {
      if (joint_name_set_.find(msg->name[index]) == joint_name_set_.end()) {
        continue;
      }
      robot_state_->setVariablePosition(msg->name[index], msg->position[index]);
      updated = true;
    }

    if (updated) {
      robot_state_->update();
      have_joint_state_ = true;
    }
  }

  void cmdVelCallback(const geometry_msgs::msg::Twist::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(command_mutex_);
    command_.pitch_rate = std::clamp(msg->angular.x, -max_pitch_rate_, max_pitch_rate_);
    command_.yaw_rate = std::clamp(msg->angular.y, -max_yaw_rate_, max_yaw_rate_);
    command_.roll_rate = std::clamp(msg->angular.z, -max_roll_rate_, max_roll_rate_);
    command_.insertion_rate =
        std::clamp(msg->linear.z, -max_insertion_rate_, max_insertion_rate_);
    last_command_time_ = now();
  }

  ar4_rcm::ToolCommand currentCommand() {
    std::lock_guard<std::mutex> lock(command_mutex_);
    if ((now() - last_command_time_).seconds() > command_timeout_) {
      command_ = ar4_rcm::ToolCommand{};
    }
    return command_;
  }

  void controlLoop() {
    if (!have_joint_state_) {
      RCLCPP_WARN_THROTTLE(
          get_logger(), *get_clock(), 2000,
          "Waiting for joint states on %s before enabling RCM control",
          joint_state_topic_.c_str());
      publishVisualization(*robot_state_, 0.0);
      return;
    }

    const double dt = 1.0 / control_rate_hz_;
    ar4_rcm::ToolCommand command = currentCommand();

    std::lock_guard<std::mutex> lock(state_mutex_);
    const double error = rcm_kinematics_->computeRcmDistance(*robot_state_);
    publishTelemetry(*robot_state_, error);

    if (error > max_rcm_error_) {
      RCLCPP_ERROR_THROTTLE(
          get_logger(), *get_clock(), 500,
          "RCM violation %.3f mm exceeds %.3f mm. Rejecting motion.",
          error * 1000.0, max_rcm_error_ * 1000.0);
      haltRobot();
      publishVisualization(*robot_state_, error);
      return;
    }

    insertion_depth_ = std::clamp(
        insertion_depth_ + command.insertion_rate * dt,
        min_insertion_depth_,
        max_insertion_depth_);
    current_direction_ = rcm_kinematics_->integrateDirection(
        rcm_kinematics_->currentToolDirection(*robot_state_),
        command.pitch_rate,
        command.yaw_rate,
        dt);

    Eigen::VectorXd qdot = rcm_kinematics_->solveJointVelocities(
        *robot_state_, command, insertion_depth_, kp_rcm_, damping_);
    limitJointVelocity(qdot);

    std::vector<double> current_positions;
    robot_state_->copyJointGroupPositions(
        rcm_kinematics_->jointModelGroup(), current_positions);

    std::vector<double> next_positions = current_positions;
    for (std::size_t index = 0; index < next_positions.size(); ++index) {
      next_positions[index] += qdot(static_cast<Eigen::Index>(index)) * dt;
    }

    moveit::core::RobotState predicted_state(*robot_state_);
    predicted_state.setJointGroupPositions(
        rcm_kinematics_->jointModelGroup(), next_positions);
    predicted_state.update();

    const double predicted_error = rcm_kinematics_->computeRcmDistance(predicted_state);
    if (predicted_error > max_rcm_error_) {
      RCLCPP_WARN_THROTTLE(
          get_logger(), *get_clock(), 500,
          "Rejected command: predicted RCM error %.3f mm exceeds %.3f mm",
          predicted_error * 1000.0, max_rcm_error_ * 1000.0);
      haltRobot();
      publishVisualization(*robot_state_, error);
      return;
    }

    if (!predicted_state.satisfiesBounds(rcm_kinematics_->jointModelGroup())) {
      RCLCPP_WARN_THROTTLE(
          get_logger(), *get_clock(), 500,
          "Rejected command: predicted joint state violates MoveIt bounds");
      haltRobot();
      publishVisualization(*robot_state_, error);
      return;
    }

    publishTrajectoryCommand(next_positions, qdot, dt);
    publishVisualization(predicted_state, predicted_error);
  }

  void limitJointVelocity(Eigen::VectorXd& qdot) const {
    if (max_joint_velocity_ <= 0.0 || qdot.size() == 0) {
      return;
    }

    const double maximum = qdot.cwiseAbs().maxCoeff();
    if (maximum > max_joint_velocity_) {
      qdot *= max_joint_velocity_ / maximum;
    }
  }

  void haltRobot() {
    std::vector<double> current_positions;
    robot_state_->copyJointGroupPositions(
        rcm_kinematics_->jointModelGroup(), current_positions);
    Eigen::VectorXd zero = Eigen::VectorXd::Zero(current_positions.size());
    publishTrajectoryCommand(current_positions, zero, 1.0 / control_rate_hz_);
  }

  void publishTrajectoryCommand(const std::vector<double>& positions,
                                const Eigen::VectorXd& qdot,
                                double dt) {
    trajectory_msgs::msg::JointTrajectory trajectory;
    trajectory.header.stamp = now();
    trajectory.joint_names = joint_names_;

    trajectory_msgs::msg::JointTrajectoryPoint point;
    point.positions = positions;
    point.velocities.resize(positions.size(), 0.0);
    for (std::size_t index = 0; index < positions.size(); ++index) {
      point.velocities[index] = qdot(static_cast<Eigen::Index>(index));
    }
    point.time_from_start = rclcpp::Duration::from_seconds(dt);
    trajectory.points.push_back(point);
    joint_pub_->publish(trajectory);
  }

  void publishTelemetry(const moveit::core::RobotState& state, double error) {
    const Eigen::Vector3d direction = rcm_kinematics_->currentToolDirection(state);
    const ar4_rcm::ToolPose pose =
        rcm_kinematics_->computeToolPose(direction, insertion_depth_, 0.0);

    geometry_msgs::msg::PoseStamped pose_msg;
    pose_msg.header.frame_id = base_frame_;
    pose_msg.header.stamp = now();
    pose_msg.pose = toPose(pose.flange_pose);
    tool_pose_pub_->publish(pose_msg);

    std_msgs::msg::Float64 error_msg;
    error_msg.data = error * 1000.0;
    error_pub_->publish(error_msg);
  }

  void publishVisualization(const moveit::core::RobotState& state, double error) {
    const rclcpp::Time stamp = now();
    const Eigen::Vector3d direction = rcm_kinematics_->currentToolDirection(state);
    const Eigen::Vector3d rcm = rcm_kinematics_->rcmPoint();
    const Eigen::Vector3d tip = rcm + insertion_depth_ * direction;
    const Eigen::Vector3d shaft_back = rcm - std::max(0.03, tool_tip_offset_ - insertion_depth_) * direction;

    tip_history_.push_back(tip);
    if (tip_history_.size() > 300) {
      tip_history_.erase(tip_history_.begin());
    }

    visualization_msgs::msg::MarkerArray markers;

    auto rcm_marker = baseMarker(base_frame_, stamp, "rcm", 0,
                                 visualization_msgs::msg::Marker::SPHERE);
    rcm_marker.pose.position = toPoint(rcm);
    rcm_marker.scale.x = 0.012;
    rcm_marker.scale.y = 0.012;
    rcm_marker.scale.z = 0.012;
    rcm_marker.color.r = 0.95;
    rcm_marker.color.g = 0.15;
    rcm_marker.color.b = 0.15;
    rcm_marker.color.a = 1.0;
    markers.markers.push_back(rcm_marker);

    auto shaft_marker = baseMarker(base_frame_, stamp, "rcm", 1,
                                   visualization_msgs::msg::Marker::LINE_STRIP);
    shaft_marker.points.push_back(toPoint(shaft_back));
    shaft_marker.points.push_back(toPoint(tip));
    shaft_marker.scale.x = 0.004;
    shaft_marker.color.r = error > max_rcm_error_ * 0.8 ? 1.0 : 0.10;
    shaft_marker.color.g = error > max_rcm_error_ * 0.8 ? 0.35 : 0.45;
    shaft_marker.color.b = 0.95;
    shaft_marker.color.a = 1.0;
    markers.markers.push_back(shaft_marker);

    auto tip_marker = baseMarker(base_frame_, stamp, "rcm", 2,
                                 visualization_msgs::msg::Marker::SPHERE);
    tip_marker.pose.position = toPoint(tip);
    tip_marker.scale.x = 0.010;
    tip_marker.scale.y = 0.010;
    tip_marker.scale.z = 0.010;
    tip_marker.color.r = 0.05;
    tip_marker.color.g = 0.85;
    tip_marker.color.b = 0.35;
    tip_marker.color.a = 1.0;
    markers.markers.push_back(tip_marker);

    auto history_marker = baseMarker(base_frame_, stamp, "rcm", 3,
                                     visualization_msgs::msg::Marker::LINE_STRIP);
    history_marker.scale.x = 0.002;
    history_marker.color.r = 0.55;
    history_marker.color.g = 0.25;
    history_marker.color.b = 0.95;
    history_marker.color.a = 0.8;
    for (const Eigen::Vector3d& history_tip : tip_history_) {
      history_marker.points.push_back(toPoint(history_tip));
    }
    markers.markers.push_back(history_marker);

    marker_pub_->publish(markers);
  }

  Eigen::Vector3d rcm_point_{0.35, 0.0, 0.35};
  Eigen::Vector3d tool_axis_local_{Eigen::Vector3d::UnitZ()};
  Eigen::Vector3d current_direction_{Eigen::Vector3d::UnitZ()};
  std::string base_frame_{"world"};
  std::string planning_group_{"arm"};
  std::string ee_link_{"link_6"};
  std::string joint_state_topic_{"/joint_states"};
  std::string command_topic_{"/rcm/cmd_vel"};
  std::string trajectory_topic_{"/joint_trajectory"};
  double tool_tip_offset_{0.20};
  double insertion_depth_{0.10};
  double min_insertion_depth_{0.02};
  double max_insertion_depth_{0.24};
  double max_rcm_error_{0.001};
  double control_rate_hz_{100.0};
  double kp_rcm_{8.0};
  double damping_{1e-3};
  double max_joint_velocity_{0.7};
  double max_pitch_rate_{0.35};
  double max_yaw_rate_{0.35};
  double max_roll_rate_{0.8};
  double max_insertion_rate_{0.03};
  double command_timeout_{0.25};
  bool have_joint_state_{false};

  moveit::core::RobotModelPtr robot_model_;
  moveit::core::RobotStatePtr robot_state_;
  std::unique_ptr<ar4_rcm::RcmKinematics> rcm_kinematics_;
  std::vector<std::string> joint_names_;
  std::unordered_set<std::string> joint_name_set_;
  std::vector<Eigen::Vector3d> tip_history_;

  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr joint_state_sub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_sub_;
  rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr joint_pub_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr tool_pose_pub_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr error_pub_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr marker_pub_;
  rclcpp::TimerBase::SharedPtr timer_;

  std::mutex state_mutex_;
  std::mutex command_mutex_;
  ar4_rcm::ToolCommand command_;
  rclcpp::Time last_command_time_{0, 0, RCL_ROS_TIME};
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<RcmControllerNode>();
  if (!node->initialize()) {
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
