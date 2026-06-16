#include "ar4_rcm_controller/rcm_kinematics.hpp"
#include <Eigen/Dense>
#include <iostream>

namespace ar4_rcm {

// Skew-symmetric matrix helper for cross product
Eigen::Matrix3d skew(const Eigen::Vector3d& v) {
  Eigen::Matrix3d m;
  m << 0.0, -v.z(), v.y(),
       v.z(), 0.0, -v.x(),
       -v.y(), v.x(), 0.0;
  return m;
}

// Pseudo-inverse helper using SVD
Eigen::MatrixXd pseudoInverse(const Eigen::MatrixXd& M, double tolerance = 1e-6) {
  Eigen::JacobiSVD<Eigen::MatrixXd> svd(M, Eigen::ComputeThinU | Eigen::ComputeThinV);
  Eigen::VectorXd singular_values = svd.singularValues();
  Eigen::VectorXd singular_values_inv = Eigen::VectorXd::Zero(singular_values.size());
  for (int i = 0; i < singular_values.size(); ++i) {
    if (singular_values(i) > tolerance) {
      singular_values_inv(i) = 1.0 / singular_values(i);
    }
  }
  return svd.matrixV() * singular_values_inv.asDiagonal() * svd.matrixU().transpose();
}

RcmKinematics::RcmKinematics(
    const moveit::core::RobotModelConstPtr& robot_model,
    const std::string& planning_group,
    const std::string& ee_link)
    : robot_model_(robot_model), ee_link_(ee_link), rcm_point_(0.0, 0.0, 0.0) {
  joint_model_group_ = robot_model_->getJointModelGroup(planning_group);
}

void RcmKinematics::setRcmPoint(const Eigen::Vector3d& rcm_point) {
  rcm_point_ = rcm_point;
}

Eigen::Vector3d RcmKinematics::computeRcmError(const moveit::core::RobotState& state) const {
  Eigen::Isometry3d T_ee = state.getGlobalLinkTransform(ee_link_);
  Eigen::Vector3d X_ee = T_ee.translation();
  Eigen::Matrix3d R_ee = T_ee.rotation();
  
  // Tool shaft axis is assumed to be along Z axis of end-effector frame
  Eigen::Vector3d u_tool = R_ee * Eigen::Vector3d(0.0, 0.0, 1.0);
  
  // Vector from EE flange to RCM
  Eigen::Vector3d X_ee_to_rcm = rcm_point_ - X_ee;
  double d = X_ee_to_rcm.dot(u_tool);
  
  // Perpendicular offset vector representing error
  Eigen::Vector3d perp_vec = X_ee_to_rcm - d * u_tool;
  return -perp_vec; // Error correction vector (towards RCM)
}

Eigen::MatrixXd RcmKinematics::computeRcmJacobian(const moveit::core::RobotState& state) const {
  Eigen::Isometry3d T_ee = state.getGlobalLinkTransform(ee_link_);
  Eigen::Vector3d X_ee = T_ee.translation();
  Eigen::Matrix3d R_ee = T_ee.rotation();
  Eigen::Vector3d u_tool = R_ee * Eigen::Vector3d(0.0, 0.0, 1.0);

  double d = (rcm_point_ - X_ee).dot(u_tool);

  // Get full 6x6 geometric Jacobian
  Eigen::MatrixXd J_geo;
  state.getJacobian(joint_model_group_, state.getLinkModel(ee_link_), Eigen::Vector3d::Zero(), J_geo);

  Eigen::MatrixXd J_pos = J_geo.block<3, 6>(0, 0);
  Eigen::MatrixXd J_rot = J_geo.block<3, 6>(3, 0);

  // Projection matrix perpendicular to tool shaft axis
  Eigen::Matrix3d P_perp = Eigen::Matrix3d::Identity() - u_tool * u_tool.transpose();

  // Analytical RCM Jacobian
  Eigen::MatrixXd J_rcm = P_perp * J_pos - d * skew(u_tool) * J_rot;
  return J_rcm;
}

Eigen::VectorXd RcmKinematics::solveJointVelocities(
    const moveit::core::RobotState& state,
    const Eigen::Vector3d& desired_tip_vel,
    double roll_vel,
    double insertion_vel,
    double kp_rcm) const {
  
  Eigen::Vector3d rcm_err = computeRcmError(state);
  Eigen::MatrixXd J_rcm = computeRcmJacobian(state);
  
  // 1. Primary task: RCM constraint velocity
  Eigen::Vector3d v_rcm_corr = kp_rcm * rcm_err;
  
  // Pseudoinverse of J_rcm
  Eigen::MatrixXd J_rcm_pinv = pseudoInverse(J_rcm);
  
  // Primary joint velocity solution
  Eigen::VectorXd q_dot_rcm = J_rcm_pinv * v_rcm_corr;
  
  // Null-space projection matrix
  Eigen::MatrixXd P_null = Eigen::MatrixXd::Identity(6, 6) - J_rcm_pinv * J_rcm;
  
  // 2. Secondary task: Tool tip coordinates movement
  Eigen::Isometry3d T_ee = state.getGlobalLinkTransform(ee_link_);
  Eigen::Vector3d X_ee = T_ee.translation();
  Eigen::Matrix3d R_ee = T_ee.rotation();
  Eigen::Vector3d u_tool = R_ee * Eigen::Vector3d(0.0, 0.0, 1.0);
  
  double d = (rcm_point_ - X_ee).dot(u_tool);
  
  // Joint Jacobian mapping for secondary task
  Eigen::MatrixXd J_geo;
  state.getJacobian(joint_model_group_, state.getLinkModel(ee_link_), Eigen::Vector3d::Zero(), J_geo);
  Eigen::MatrixXd J_pos = J_geo.block<3, 6>(0, 0);
  Eigen::MatrixXd J_rot = J_geo.block<3, 6>(3, 0);
  
  // Tool tip Jacobian relative to joint velocities
  // X_tip = X_rcm + s * u_tool
  // tip velocity mapping includes flange position and shaft rotation
  Eigen::MatrixXd J_tip = J_pos - d * skew(u_tool) * J_rot;
  
  // Project task Jacobian into RCM null-space
  Eigen::MatrixXd J_task_proj = J_tip * P_null;
  
  // Secondary joint velocity solution
  Eigen::Vector3d v_task = desired_tip_vel;
  Eigen::VectorXd q_dot_task = pseudoInverse(J_task_proj) * (v_task - J_tip * q_dot_rcm);
  
  // Combine primary and secondary tasks
  Eigen::VectorXd q_dot_final = q_dot_rcm + P_null * q_dot_task;
  
  // Incorporate roll joint velocity directly into joint 6 (flange roll)
  q_dot_final(5) += roll_vel;
  
  return q_dot_final;
}

} // namespace ar4_rcm
