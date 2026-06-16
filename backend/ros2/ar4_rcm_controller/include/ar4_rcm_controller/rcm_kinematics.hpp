#ifndef AR4_RCM_CONTROLLER__RCM_KINEMATICS_HPP_
#define AR4_RCM_CONTROLLER__RCM_KINEMATICS_HPP_

#include <Eigen/Dense>
#include <moveit/robot_model/robot_model.h>
#include <moveit/robot_state/robot_state.h>
#include <vector>

namespace ar4_rcm {

class RcmKinematics {
public:
  RcmKinematics(const moveit::core::RobotModelConstPtr& robot_model,
                const std::string& planning_group,
                const std::string& ee_link);

  // Set RCM point in base frame
  void setRcmPoint(const Eigen::Vector3d& rcm_point);

  // Compute RCM error (distance from shaft line to RCM point)
  Eigen::Vector3d computeRcmError(const moveit::core::RobotState& state) const;

  // Compute RCM Jacobian matrix
  Eigen::MatrixXd computeRcmJacobian(const moveit::core::RobotState& state) const;

  // Solve joint velocity command using Null-space projection
  Eigen::VectorXd solveJointVelocities(
      const moveit::core::RobotState& state,
      const Eigen::Vector3d& desired_tip_vel,
      double roll_vel,
      double insertion_vel,
      double kp_rcm = 5.0) const;

private:
  moveit::core::RobotModelConstPtr robot_model_;
  const moveit::core::JointModelGroup* joint_model_group_;
  std::string ee_link_;
  Eigen::Vector3d rcm_point_;
};

} // namespace ar4_rcm

#endif // AR4_RCM_CONTROLLER__RCM_KINEMATICS_HPP_
