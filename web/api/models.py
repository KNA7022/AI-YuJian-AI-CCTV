from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["draft", "calibrating", "queued", "running", "succeeded", "failed", "cancelled"]


class JobConfig(BaseModel):
    language: Literal["zh", "en"] = "zh"
    pose_family: Literal["rtmpose", "rtmo", "yolo-pose"] = "rtmpose"
    pose_mode: Literal["lightweight", "balanced", "performance"] = "balanced"
    yolo_pose_model: str = "yolo11n-pose.pt"
    keep_audio: bool = True
    visualize_positions: bool = True
    ball_model_path: str = "weights/yolo11s-ball.pt"
    trim_enabled: bool = False
    trim_start_sec: float | None = None
    trim_end_sec: float | None = None


class JobRecord(BaseModel):
    id: str
    name: str
    status: JobStatus
    video_path: str
    template_frame_path: str | None = None
    calibration_points: list[list[int]] | None = None
    config_json: JobConfig
    output_dir: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime


class ArtifactRecord(BaseModel):
    job_id: str
    type: str
    path: str
    mime_type: str


class CalibrationPayload(BaseModel):
    frame_time_sec: float = Field(default=0.0, ge=0)
    corners: list[list[int]] = Field(min_length=4, max_length=4)


class StartJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class SystemHealth(BaseModel):
    ffmpeg_available: bool
    disk_free_bytes: int
    queued_jobs: int
    running_job_id: str | None = None
