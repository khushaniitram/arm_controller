#include "ar4_rcm_controller/rcm_kinematics.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace ar4_rcm {

Eigen::Matrix3d RcmKinematics::skew(const Eigen::Vector3d& vector) {
  Eigen::Matrix3d matrix;
  matrix << 0.0, -vector.z(), vector.y(),
            vector.z(), 0.0, -vector.x(),
            -vector.y(), vector.x(), 0.0;
  return matrix;
}

Eigen::MatrixXd RcmKinematics::dampedPseudoInverse(const Eigen::MatrixXd& matrix,
                                                   double damping) {
  Eigen::JacobiSVD<Eigen::MatrixXd> svd(
      matrix, Eigen::ComputeThinU | Eigen::ComputeThinV);
  const Eigen::VectorXd singular_values = svd.singularValues();
  Eigen::VectorXd inverted = Eigen::VectorXd::Zero(singular_values.size());
  const double lambda_squared = damping * damping;

  for (int index = 0; index < singular_values.size(); ++index) {
    const double value = singular_values(index);
    inverted(index) = value / ((value * value) + lambda_squared);
  }

  return svd.matrixV() * inverted.asDiagonal() * svd.matrixU().transpose();
}

Eigen::Isometry3d RcmKinematics::poseFromDirectionRoll(
    const Eigen::Vector3d& position,
    const Eigen::Vector3d& direction,
    double roll_angle) {
  Eigen::Vector3d z_axis = direction.normalized();
  if (z_axis.norm() < 1e-9) {
    z_axis = Eigen::Vector3d::UnitZ();
  }

  Eigen::Vector3d reference = Eigen::Vector3d::UnitZ();
  if (std::abs(z_axis.dot(reference)) > 0.95) {
    reference = Eigen::Vector3d::UnitX();
  }

  Eigen::Vector3d x_axis = reference.cross(z_axis).normalized();
  Eigen::Vector3d y_axis = z_axis.cross(x_axis).normalized();

  Eigen::AngleAxisd roll_rotation(roll_angle, z_axis);
  x_axis = roll_rotation * x_axis;
  y_axis = roll_rotation * y_axis;

  Eigen::Isometry3d pose = Eigen::Isometry3d::Identity();
  pose.linear().col(0) = x_axis;
  pose.linear().col(1) = y_axis;
  pose.linear().col(2) = z_axis;
  pose.translation() = position;
  return pose;
}

RcmKinematics::RcmKinematics(
    const moveit::core::RobotModelConstPtr& robot_model,
    const std::string& planning_group,
    const std::string& ee_link)
    : robot_model_(robot_model), ee_link_(ee_link) {
  if (!robot_model_) {
    throw std::invalid_argument("RcmKinematics requires a valid RobotModel");
  }

  joint_model_group_ = robot_model_->getJointModelGroup(planning_group);
  if (joint_model_group_ == nullptr) {
    throw std::invalid_argument("Unknown MoveIt planning group: " + planning_group);
  }

  if (robot_model_->getLinkModel(ee_link_) == nullptr) {
    throw std::invalid_argument("Unknown end-effector link: " + ee_link_);
  }
}

void RcmKinematics::setRcmPoint(const Eigen::Vector3d& rcm_point) {
  rcm_point_ = rcm_point;
}

void RcmKinematics::setToolAxisLocal(const Eigen::Vector3d& axis) {
  if (axis.norm() < 1e-9) {
    throw std::invalid_argument("Tool axis must be non-zero");
  }
  tool_axis_local_ = axis.normalized();
}

void RcmKinematics::setToolTipOffset(double offset_m) {
  tool_tip_offset_ = offset_m;
}

const Eigen::Vector3d& RcmKinematics::rcmPoint() const {
  return rcm_point_;
}

const std::string& RcmKinematics::eeLink() const {
  return ee_link_;
}

const moveit::core::JointModelGroup* RcmKinematics::jointModelGroup() const {
  return joint_model_group_;
}

Eigen::Vector3d RcmKinematics::currentToolDirection(
    const moveit::core::RobotState& state) const {
  const Eigen::Isometry3d transform = state.getGlobalLinkTransform(ee_link_);
  return (transform.rotation() * tool_axis_local_).normalized();
}

Eigen::Vector3d RcmKinematics::computeRcmError(
    const moveit::core::RobotState& state) const {
  const Eigen::Isometry3d transform = state.getGlobalLinkTransform(ee_link_);
  const Eigen::Vector3d flange_position = transform.translation();
  const Eigen::Vector3d tool_direction = currentToolDirection(state);
  const Eigen::Vector3d flange_to_rcm = rcm_point_ - flange_position;
  const double signed_distance_along_tool = flange_to_rcm.dot(tool_direction);
  return flange_to_rcm - signed_distance_along_tool * tool_direction;
}

double RcmKinematics::computeRcmDistance(
    const moveit::core::RobotState& state) const {
  return computeRcmError(state).norm();
}

Eigen::MatrixXd RcmKinematics::computeRcmJacobian(
    const moveit::core::RobotState& state) const {
  const Eigen::Isometry3d transform = state.getGlobalLinkTransform(ee_link_);
  const Eigen::Vector3d flange_position = transform.translation();
  const Eigen::Vector3d tool_direction = currentToolDirection(state);
  const double rcm_to_flange_distance =
      (rcm_point_ - flange_position).dot(tool_direction);

  Eigen::MatrixXd geometric_jacobian;
  state.getJacobian(joint_model_group_,
                    state.getLinkModel(ee_link_),
                    Eigen::Vector3d::Zero(),
                    geometric_jacobian);

  const std::size_t variable_count = joint_model_group_->getVariableCount();
  const Eigen::MatrixXd position_jacobian =
      geometric_jacobian.block(0, 0, 3, variable_count);
  const Eigen::MatrixXd angular_jacobian =
      geometric_jacobian.block(3, 0, 3, variable_count);

  const Eigen::Matrix3d perpendicular_projection =
      Eigen::Matrix3d::Identity() - tool_direction * tool_direction.transpose();

  return perpendicular_projection * position_jacobian -
         rcm_to_flange_distance * skew(tool_direction) * angular_jacobian;
}

ToolPose RcmKinematics::computeToolPose(const Eigen::Vector3d& direction,
                                        double insertion_depth,
                                        double roll_angle) const {
  ToolPose pose;
  pose.direction = direction.normalized();
  pose.insertion_depth = insertion_depth;
  pose.roll_angle = roll_angle;
  pose.tip_position = rcm_point_ + insertion_depth * pose.direction;

  const Eigen::Vector3d flange_position =
      pose.tip_position - tool_tip_offset_ * pose.direction;
  pose.flange_pose = poseFromDirectionRoll(flange_position, pose.direction, roll_angle);
  return pose;
}

Eigen::Vector3d RcmKinematics::integrateDirection(const Eigen::Vector3d& direction,
                                                  double pitch_rate,
                                                  double yaw_rate,
                                                  double dt) const {
  const Eigen::Isometry3d tool_frame =
      poseFromDirectionRoll(Eigen::Vector3d::Zero(), direction, 0.0);
  const Eigen::Vector3d pitch_axis = tool_frame.rotation().col(0);
  const Eigen::Vector3d yaw_axis = tool_frame.rotation().col(1);
  const Eigen::Vector3d angular_velocity =
      pitch_rate * pitch_axis + yaw_rate * yaw_axis;
  Eigen::Vector3d integrated = direction + angular_velocity.cross(direction) * dt;

  if (integrated.norm() < 1e-9) {
    return direction.normalized();
  }

  return integrated.normalized();
}

Eigen::VectorXd RcmKinematics::solveJointVelocities(
    const moveit::core::RobotState& state,
    const ToolCommand& command,
    double insertion_depth,
    double kp_rcm,
    double damping) const {
  const Eigen::Vector3d rcm_error = computeRcmError(state);
  const Eigen::Vector3d tool_direction = currentToolDirection(state);
  const Eigen::MatrixXd rcm_jacobian = computeRcmJacobian(state);
  const Eigen::MatrixXd rcm_jacobian_pinv =
      dampedPseudoInverse(rcm_jacobian, damping);
  const Eigen::Vector3d desired_rcm_velocity = kp_rcm * rcm_error;

  const Eigen::VectorXd qdot_rcm =
      rcm_jacobian_pinv * desired_rcm_velocity;
  const std::size_t variable_count = joint_model_group_->getVariableCount();
  const Eigen::MatrixXd null_space =
      Eigen::MatrixXd::Identity(variable_count, variable_count) -
      rcm_jacobian_pinv * rcm_jacobian;

  Eigen::MatrixXd geometric_jacobian;
  state.getJacobian(joint_model_group_,
                    state.getLinkModel(ee_link_),
                    Eigen::Vector3d::Zero(),
                    geometric_jacobian);

  const Eigen::MatrixXd position_jacobian =
      geometric_jacobian.block(0, 0, 3, variable_count);
  const Eigen::MatrixXd angular_jacobian =
      geometric_jacobian.block(3, 0, 3, variable_count);

  const Eigen::MatrixXd tip_jacobian =
      position_jacobian - tool_tip_offset_ * skew(tool_direction) * angular_jacobian;

  const Eigen::Isometry3d tool_frame =
      poseFromDirectionRoll(Eigen::Vector3d::Zero(), tool_direction, 0.0);
  const Eigen::Vector3d pivot_angular_velocity =
      command.pitch_rate * tool_frame.rotation().col(0) +
      command.yaw_rate * tool_frame.rotation().col(1);
  const Eigen::Vector3d desired_tip_velocity =
      insertion_depth * pivot_angular_velocity.cross(tool_direction) +
      command.insertion_rate * tool_direction;

  const Eigen::MatrixXd projected_tip_jacobian = tip_jacobian * null_space;
  const Eigen::VectorXd qdot_tip =
      dampedPseudoInverse(projected_tip_jacobian, damping) *
      (desired_tip_velocity - tip_jacobian * qdot_rcm);

  Eigen::VectorXd qdot = qdot_rcm + null_space * qdot_tip;

  const Eigen::RowVectorXd roll_jacobian =
      tool_direction.transpose() * angular_jacobian;
  const Eigen::MatrixXd projected_roll_jacobian = roll_jacobian * null_space;
  if (projected_roll_jacobian.norm() > 1e-9) {
    const double current_roll_rate = (roll_jacobian * qdot)(0);
    qdot += null_space *
            (dampedPseudoInverse(projected_roll_jacobian, damping) *
             Eigen::VectorXd::Constant(1, command.roll_rate - current_roll_rate));
  }

  qdot += rcm_jacobian_pinv * (desired_rcm_velocity - rcm_jacobian * qdot);
  return qdot;
}

} // namespace ar4_rcm
