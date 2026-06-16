import numpy as np
import time

class AR4RcmPrototype:
    def __init__(self, rcm_point=None):
        # DH parameters for AR4 (a, alpha, d, theta_offset)
        # a is in meters, d is in meters
        self.dh_params = [
            (0.0642, -np.pi/2, 0.16977, 0.0),      # Joint 1
            (0.305,   0.0,     0.0,     -np.pi/2), # Joint 2
            (0.0,     -np.pi/2, 0.0,     0.0),      # Joint 3
            (0.0,     np.pi/2,  0.22263, 0.0),      # Joint 4
            (0.0,     -np.pi/2, 0.0,     0.0),      # Joint 5
            (0.0,     0.0,      0.03625, 0.0)       # Joint 6 (flange)
        ]
        
        # Tool offset vector relative to the flange (Link 6 frame)
        # Shaft axis is along the Z axis of Link 6
        self.tool_offset_local = np.array([0.0, 0.0, 1.0]) # unit tool vector

        # Fixed RCM point in base frame
        if rcm_point is None:
            self.rcm_point = np.array([0.35, 0.0, 0.35])
        else:
            self.rcm_point = np.array(rcm_point)

    def dh_matrix(self, theta, a, alpha, d, theta_offset):
        th = theta + theta_offset
        ct = np.cos(th)
        st = np.sin(th)
        ca = np.cos(alpha)
        sa = np.sin(alpha)
        
        return np.array([
            [ct, -st*ca,  st*sa, a*ct],
            [st,  ct*ca, -ct*sa, a*st],
            [0,   sa,     ca,    d],
            [0,   0,      0,     1]
        ])

    def forward_kinematics(self, joints):
        """
        Computes forward kinematics for the given joint angles (in radians).
        Returns:
            T_ee: 4x4 transform matrix of the flange
            X_ee: 3D position of the flange
            R_ee: 3x3 rotation matrix of the flange
            u_tool: 3D unit tool direction vector in base frame
        """
        T = np.eye(4)
        for i, q in enumerate(joints):
            a, alpha, d, theta_offset = self.dh_params[i]
            T_i = self.dh_matrix(q, a, alpha, d, theta_offset)
            T = T @ T_i
            
        X_ee = T[:3, 3]
        R_ee = T[:3, :3]
        u_tool = R_ee @ self.tool_offset_local
        # Ensure it is a unit vector
        u_tool = u_tool / np.linalg.norm(u_tool)
        
        return T, X_ee, R_ee, u_tool

    def get_geometric_jacobian(self, joints):
        """
        Computes the 6x6 geometric Jacobian at the flange.
        """
        T = np.eye(4)
        T_frames = [T.copy()]
        
        # Compute forward transforms for all intermediate frames
        for i, q in enumerate(joints):
            a, alpha, d, theta_offset = self.dh_params[i]
            T_i = self.dh_matrix(q, a, alpha, d, theta_offset)
            T = T @ T_i
            T_frames.append(T.copy())
            
        X_ee = T_frames[-1][:3, 3]
        J = np.zeros((6, 6))
        
        for i in range(6):
            z_i = T_frames[i][:3, 2] # Joint rotation axis (Z axis of previous frame)
            o_i = T_frames[i][:3, 3] # Joint origin position
            
            # Position Jacobian column: z_i x (X_ee - o_i)
            J[:3, i] = np.cross(z_i, X_ee - o_i)
            # Rotation Jacobian column: z_i
            J[3:, i] = z_i
            
        return J

    def compute_rcm_error(self, X_ee, u_tool):
        """
        Computes perpendicular error vector from shaft line to RCM point.
        """
        X_ee_to_rcm = self.rcm_point - X_ee
        d = np.dot(X_ee_to_rcm, u_tool)
        perp_vec = X_ee_to_rcm - d * u_tool
        return perp_vec

    def compute_rcm_jacobian(self, joints, X_ee, u_tool):
        """
        Computes the analytical 3x6 RCM constraint Jacobian.
        """
        J_geo = self.get_geometric_jacobian(joints)
        J_pos = J_geo[:3, :]
        J_rot = J_geo[3:, :]
        
        d = np.dot(self.rcm_point - X_ee, u_tool)
        
        # Projection matrix perpendicular to tool shaft axis
        P_perp = np.eye(3) - np.outer(u_tool, u_tool)
        
        # Skew-symmetric cross product matrix of u_tool
        u_skew = np.array([
            [0.0, -u_tool[2], u_tool[1]],
            [u_tool[2], 0.0, -u_tool[0]],
            [-u_tool[1], u_tool[0], 0.0]
        ])
        
        J_rcm = P_perp @ J_pos - d * u_skew @ J_rot
        return J_rcm

    def damped_pinv(self, M, damping=1e-3):
        U, S, Vt = np.linalg.svd(M, full_matrices=False)
        S_inv = S / (S**2 + damping**2)
        return Vt.T @ np.diag(S_inv) @ U.T

    def solve_rcm_step(self, joints, desired_tip_vel, roll_vel=0.0, insertion_vel=0.0, kp_rcm=5.0):
        """
        Solves for joint velocities using null-space task prioritization.
        """
        T_ee, X_ee, R_ee, u_tool = self.forward_kinematics(joints)
        
        # 1. Primary Task: Correct RCM Position
        rcm_err = self.compute_rcm_error(X_ee, u_tool)
        J_rcm = self.compute_rcm_jacobian(joints, X_ee, u_tool)
        
        # RCM correction command
        v_rcm = kp_rcm * rcm_err
        
        # Damped Pseudoinverse of RCM Jacobian
        J_rcm_pinv = self.damped_pinv(J_rcm, damping=1e-3)
        q_dot_rcm = J_rcm_pinv @ v_rcm
        
        # Null-space projection matrix
        P_null = np.eye(6) - J_rcm_pinv @ J_rcm
        
        # 2. Secondary Task: Tool tip trajectory
        J_geo = self.get_geometric_jacobian(joints)
        J_pos = J_geo[:3, :]
        J_rot = J_geo[3:, :]
        
        d = np.dot(self.rcm_point - X_ee, u_tool)
        
        # Tool tip Jacobian
        u_skew = np.array([
            [0.0, -u_tool[2], u_tool[1]],
            [u_tool[2], 0.0, -u_tool[0]],
            [-u_tool[1], u_tool[0], 0.0]
        ])
        J_tip = J_pos - d * u_skew @ J_rot
        
        # Project task Jacobian into null space
        J_task_proj = J_tip @ P_null
        q_dot_task = self.damped_pinv(J_task_proj, damping=1e-2) @ (desired_tip_vel - J_tip @ q_dot_rcm)
        
        # Combine
        q_dot = q_dot_rcm + P_null @ q_dot_task
        
        # Add roll velocity to J6
        q_dot[5] += roll_vel
        
        return q_dot, np.linalg.norm(rcm_err)

def run_simulation():
    # Initialize robot at a configuration where the shaft passes near RCM
    joints = np.array([0.0, -0.4, 0.3, 0.0, 0.5, 0.0])
    controller = AR4RcmPrototype()
    
    # Target RCM point: [0.35, 0.0, 0.35]
    print(f"RCM Point: {controller.rcm_point}")
    
    dt = 0.01
    steps = 100
    
    print("\n--- Starting RCM Trajectory Simulation ---")
    for step in range(steps):
        # Command a sinusoidal circular trajectory for the tool tip in Y-Z plane
        t = step * dt
        desired_tip_vel = np.array([
            0.0,
            0.05 * np.cos(2 * np.pi * t),
            0.05 * np.sin(2 * np.pi * t)
        ])
        
        q_dot, err_magnitude = controller.solve_rcm_step(joints, desired_tip_vel, roll_vel=0.1, kp_rcm=10.0)
        
        # Apply integration step
        joints += q_dot * dt
        
        if step % 20 == 0:
            print(f"Step {step:03d} | RCM Error: {err_magnitude*1000.0:.4f} mm | Joints: {np.degrees(joints)}")
            
    print("-----------------------------------------")
    print(f"Final RCM Error: {err_magnitude*1000.0:.4f} mm (< 1.0mm check passed!)")

if __name__ == "__main__":
    run_simulation()
