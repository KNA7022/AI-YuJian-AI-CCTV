export type JobStatus = "draft" | "calibrating" | "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface JobConfig {
  language: "zh" | "en";
  pose_family: "rtmpose" | "rtmo" | "yolo-pose";
  pose_mode: "lightweight" | "balanced" | "performance";
  yolo_pose_model: string;
  keep_audio: boolean;
  visualize_positions: boolean;
  ball_model_path: string;
  trim_enabled: boolean;
  trim_start_sec: string | number | null;
  trim_end_sec: string | number | null;
}

export interface ArtifactRecord {
  job_id: string;
  type: string;
  path: string;
  mime_type: string;
}

export interface JobRecord {
  id: string;
  name: string;
  status: JobStatus;
  video_path: string;
  template_frame_path?: string | null;
  calibration_points?: number[][] | null;
  config_json: JobConfig;
  output_dir: string;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at: string;
  artifacts?: ArtifactRecord[];
  summary?: SessionSummary;
}

export interface SessionSummary {
  job_id: string;
  video_name: string;
  status: string;
  processing_time_sec: number;
  warnings: string[];
  artifacts: Record<string, string>;
  stats: {
    rallies: number;
    fps: number;
    frame_width: number;
    frame_height: number;
    movement?: Record<string, unknown>;
  };
}

export interface JobEvent {
  type: "status" | "progress";
  status?: string;
  stage?: string;
  progress?: number;
  message?: string;
  summary?: SessionSummary;
  timestamp?: string;
}
