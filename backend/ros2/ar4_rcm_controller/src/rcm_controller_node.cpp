#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <trajectory_msgs/msg/joint_trajectory.hpp>
#include <trajectory_msgs/msg/joint_trajectory_point.hpp>
#include <moveit/robot_model_loader/robot_model_loader.h>
#include <moveit/robot_state/robot_state.h>
#include "ar4_rcm_controller/rcm_kinematics.hpp"

class RcmControllerNode : public rclcpp::Node {
public:
  RcmControllerNode() : Node("rcm_controller_node") {
    // 1. Declare parameters
    this->declare_parameter<double>("rcm_x", 0.3);
    this->declare_parameter<double>("rcm_y", 0.0);
    this->declare_parameter<double>("rcm_z", 0.4);
    this->declare_parameter<double>("max_rcm_error", 0.0015); // 1.5mm safety threshold

    // Load parameters
    rcm_point_ << this->get_parameter("rcm_x").as_double(),
                  this->get_parameter("rcm_y").as_double(),
                  this->get_parameter("rcm_z").as_double();
    max_rcm_error_ = this->get_parameter("max_rcm_error").as_double();

    RCLCPP_INFO(this->get_logger(), "Starting RCM Controller with RCM Point: (%.3f, %.3f, %.3f)", 
                rcm_point_.x(), rcm_point_.y(), rcm_point_.z());

    // 2. Initialize Robot Model & Kinematics
    robot_model_loader::RobotModelLoader robot_model_loader(shared_from_this(), "robot_description");
    robot_model_ = robot_model_loader.getModel();
    if (!robot_model_) {
      RCLCPP_FATAL(this->get_logger(), "Failed to load robot model from robot_description!");
      rclcpp::shutdown();
      return;
    }
    
    robot_state_ = std::make_shared<moveit::core::RobotState>(robot_model_);
    robot_state_->setToDefaultValues();

    // Planning group & Flange link definition
    std::string planning_group = "arm";
    std::string ee_link = "link_6"; // Tool flange
    rcm_kinematics_ = std::make_unique<ar4_rcm::RcmKinematics>(robot_model_, planning_group, ee_link);
    rcm_kinematics_->setRcmPoint(rcm_point_);

    // 3. Subscriptions & Publishers
    joint_state_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
        "/joint_states", 10, std::bind(&RcmControllerNode::jointStateCallback, this, std::placeholders::_1));

    cmd_vel_sub_ = this->create_subscription<geometry_msgs::msg::Twist>(
        "/rcm/cmd_vel", 10, std::bind(&RcmControllerNode::cmdVelCallback, this, std::placeholders::_1));

    joint_pub_ = this->create_publisher<trajectory_msgs::msg::JointTrajectory>("/joint_trajectory", 10);

    // 4. Controller timer running at 100 Hz
    timer_ = this->create_wall_timer(std::chrono::milliseconds(10), std::bind(&RcmControllerNode::controlLoop, this));
  }

private:
  void jointStateCallback(const sensor_msgs::msg::JointState::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    for (size_t i = 0; i < msg->name.size(); ++i) {
      robot_state_->setJointPositions(msg->name[i], &msg->position[i]);
    }
  }

  void cmdVelCallback(const geometry_msgs::msg::Twist::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(cmd_mutex_);
    // linear x,y,z commands translate the tool tip
    desired_tip_vel_ << msg->linear.x, msg->linear.y, msg->linear.z;
    roll_vel_ = msg->angular.z;  // Roll about axis
    insertion_vel_ = msg->linear.z; // Insertion along axis
  }

  void controlLoop() {
    std::lock_guard<std::mutex> lock_state(state_mutex_);
    std::lock_guard<std::mutex> lock_cmd(cmd_mutex_);

    // Compute live RCM error and check safety constraint
    Eigen::Vector3d rcm_err = rcm_kinematics_->computeRcmError(*robot_state_);
    double rcm_err_magnitude = rcm_err.norm();

    if (rcm_err_magnitude > max_rcm_error_) {
      RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 500,
                            "RCM Safety Violation! Error magnitude: %.4f mm (limit: %.4f mm). Halting motion.",
                            rcm_err_magnitude * 1000.0, max_rcm_error_ * 1000.0);
      haltRobot();
      return;
    }

    // Solve joint velocities
    Eigen::VectorXd q_dot = rcm_kinematics_->solveJointVelocities(*robot_state_, desired_tip_vel_, roll_vel_, insertion_vel_);

    // Publish command
    publishTrajectoryCommand(q_dot);
  }

  void haltRobot() {
    trajectory_msgs::msg::JointTrajectory traj_msg;
    traj_msg.header.stamp = this->now();
    traj_msg.joint_names = {"joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"};
    
    trajectory_msgs::msg::JointTrajectoryPoint point;
    point.positions = std::vector<double>(6, 0.0);
    // Get current positions
    robot_state_->copyJointGroupPositions("arm", point.positions);
    point.velocities = std::vector<double>(6, 0.0);
    point.time_from_start = rclcpp::Duration::from_seconds(0.01);
    traj_msg.points.push_back(point);
    
    joint_pub_->publish(traj_msg);
  }

  void publishTrajectoryCommand(const Eigen::VectorXd& q_dot) {
    trajectory_msgs::msg::JointTrajectory traj_msg;
    traj_msg.header.stamp = this->now();
    traj_msg.joint_names = {"joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"};

    trajectory_msgs::msg::JointTrajectoryPoint point;
    point.positions.resize(6);
    point.velocities.resize(6);
    
    std::vector<double> current_q(6);
    robot_state_->copyJointGroupPositions("arm", current_q);

    double dt = 0.01; // 10ms loop step
    for (int i = 0; i < 6; ++i) {
      // Numerical integration to compute next joint positions
      point.positions[i] = current_q[i] + q_dot(i) * dt;
      point.velocities[i] = q_dot(i);
    }
    point.time_from_start = rclcpp::Duration::from_seconds(dt);
    traj_msg.points.push_back(point);

    joint_pub_->publish(traj_msg);
  }

  Eigen::Vector3d rcm_point_;
  double max_rcm_error_;

  moveit::core::RobotModelPtr robot_model_;
  moveit::core::RobotStatePtr robot_state_;
  std::unique_ptr<ar4_rcm::RcmKinematics> rcm_kinematics_;

  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr joint_state_sub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_sub_;
  rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr joint_pub_;
  rclcpp::TimerBase::SharedPtr timer_;

  std::mutex state_mutex_;
  std::mutex cmd_mutex_;

  Eigen::Vector3d desired_tip_vel_ = Eigen::Vector3d::Zero();
  double roll_vel_ = 0.0;
  double insertion_vel_ = 0.0;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<RcmControllerNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
