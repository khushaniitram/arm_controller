export interface RobotTelemetry {
  x?: number;
  y?: number;
  z?: number;
  j1?: number;
  j2?: number;
  j3?: number;
  j4?: number;
  j5?: number;
  j6?: number;
  mode?: string;
  speed?: number;
  connected?: boolean;
  port?: string | null;
  error?: string | null;
  controller_message?: string | null;
  motion_error?: string | null;
  moving_to_coords?: boolean;
  feedback_ready?: boolean;
  feedback_age_ms?: number | null;
  position_source?: string;
}
