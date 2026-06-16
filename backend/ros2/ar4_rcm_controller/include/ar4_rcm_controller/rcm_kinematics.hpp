#ifndef AR4_RCM_CONTROLLER__RCM_KINEMATICS_HPP_
#define AR4_RCM_CONTROLLER__RCM_KINEMATICS_HPP_

#include <Eigen/Dense>
#include <moveit/robot_model/robot_model.h>
#include <moveit/robot_state/robot_state.h>
#include <string>
#include <vector>

namespace ar4_rcm {

struct ToolCommand {
  double pitch_rate{0.0};
  double yaw_rate{0.0};
  double roll_rate{0.0};
  double insertion_rate{0.0};
};

struct ToolPose {
  Eigen::Vector3d direction{Eigen::Vector3d::UnitZ()};
  Eigen::Vector3d tip_position{Eigen::Vector3d::Zero()};
  Eigen::Isometry3d flange_pose{Eigen::Isometry3d::Identity()};
  double insertion_depth{0.0};
  double roll_angle{0.0};
};

class RcmKinematics {
public:
  RcmKinematics(const moveit::core::RobotModelConstPtr& robot_model,
                const std::string& planning_group,
                const std::string& ee_link);

  void setRcmPoint(const Eigen::Vector3d& rcm_point);
  void setToolAxisLocal(const Eigen::Vector3d& axis);
  void setToolTipOffset(double offset_m);

  const Eigen::Vector3d& rcmPoint() const;
  const std::string& eeLink() const;
  const moveit::core::JointModelGroup* jointModelGroup() const;

  Eigen::Vector3d currentToolDirection(const moveit::core::RobotState& state) const;
  Eigen::Vector3d computeRcmError(const moveit::core::RobotState& state) const;
  double computeRcmDistance(const moveit::core::RobotState& state) const;
  Eigen::MatrixXd computeRcmJacobian(const moveit::core::RobotState& state) const;

  ToolPose computeToolPose(const Eigen::Vector3d& direction,
                           double insertion_depth,
                           double roll_angle) const;

  Eigen::Vector3d integrateDirection(const Eigen::Vector3d& direction,
                                     double pitch_rate,
                                     double yaw_rate,
                                     double dt) const;

  Eigen::VectorXd solveJointVelocities(
      const moveit::core::RobotState& state,
      const ToolCommand& command,
      double insertion_depth,
      double kp_rcm,
      double damping) const;

  static Eigen::Matrix3d skew(const Eigen::Vector3d& vector);
  static Eigen::MatrixXd dampedPseudoInverse(const Eigen::MatrixXd& matrix,
                                             double damping);
  static Eigen::Isometry3d poseFromDirectionRoll(const Eigen::Vector3d& position,
                                                 const Eigen::Vector3d& direction,
                                                 double roll_angle);

private:
  moveit::core::RobotModelConstPtr robot_model_;
  const moveit::core::JointModelGroup* joint_model_group_{nullptr};
  std::string ee_link_;
  Eigen::Vector3d rcm_point_{Eigen::Vector3d::Zero()};
  Eigen::Vector3d tool_axis_local_{Eigen::Vector3d::UnitZ()};
  double tool_tip_offset_{0.0};
};

} // namespace ar4_rcm

#endif // AR4_RCM_CONTROLLER__RCM_KINEMATICS_HPP_
