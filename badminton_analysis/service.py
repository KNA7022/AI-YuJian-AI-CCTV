import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable

from .data.writer import write_json
from .system import BadmintonAnalysisSystem, load_runtime_dependencies


ProgressCallback = Callable[[dict], None]
CancelCallback = Callable[[], bool]


@dataclass
class AnalysisConfig:
    job_id: str
    video_path: str
    output_dir: str
    template_path: str
    calibration_path: str
    ball_model_path: str = "weights/yolo11s-ball.pt"
    pose_family: str = "rtmpose"
    pose_mode: str = "balanced"
    yolo_pose_model: str = "yolo11n-pose.pt"
    show_pose_roi: bool = True
    keep_audio: bool = True
    language: str = "zh"
    visualize_positions: bool = True
    metadata: dict = field(default_factory=dict)


def _default_progress(event: dict) -> None:
    return None


def _default_cancel() -> bool:
    return False


def _build_summary(config: AnalysisConfig, started_at: float, ended_at: float, system: BadmintonAnalysisSystem, warnings: list[str]) -> dict:
    output_dir = system.save_dir
    visualizations_dir = os.path.join(output_dir, "position_visualizations")
    artifacts = {
        "annotated_video": system.output_video_path if os.path.exists(system.output_video_path) else None,
        "detections": system.detections_path if os.path.exists(system.detections_path) else None,
        "metadata": system.metadata_path if os.path.exists(system.metadata_path) else None,
        "match_heatmap": os.path.join(visualizations_dir, "heatmaps", "match_heatmap.png"),
        "match_scatter": os.path.join(visualizations_dir, "scatter_plots", "match_scatter.png"),
        "visualizations_dir": visualizations_dir if os.path.exists(visualizations_dir) else None,
    }
    artifacts = {
        key: value for key, value in artifacts.items()
        if value is not None and (key.endswith("_dir") or os.path.exists(value))
    }

    summary = {
        "job_id": config.job_id,
        "video_name": system.video_name,
        "status": "succeeded",
        "processing_time_sec": round(ended_at - started_at, 3),
        "language": config.language,
        "pose_family": config.pose_family,
        "pose_mode": config.pose_mode,
        "keep_audio": config.keep_audio,
        "warnings": warnings,
        "artifacts": artifacts,
        "stats": {
            "rallies": int(system.rally_count),
            "fps": float(system.fps),
            "frame_width": int(system.frame_width),
            "frame_height": int(system.frame_height),
        },
        "source": {
            "video_path": config.video_path,
            "template_path": config.template_path,
            "calibration_path": config.calibration_path,
        },
        "metadata": config.metadata,
    }
    if not getattr(system, "ball_model_available", True):
        summary["warnings"].append("Shuttlecock model missing; result generated without shuttlecock detection.")
    return summary


def run_analysis(
    config: AnalysisConfig,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> dict:
    load_runtime_dependencies()
    progress_callback = progress_callback or _default_progress
    cancel_callback = cancel_callback or _default_cancel

    if cancel_callback():
        raise RuntimeError("Analysis cancelled before start")

    os.makedirs(config.output_dir, exist_ok=True)
    started_at = time.time()
    warnings: list[str] = []

    progress_callback({"stage": "initializing", "progress": 2, "message": "Initializing analysis runtime"})

    system = BadmintonAnalysisSystem(
        video_path=config.video_path,
        show_display=False,
        show_skeletons=True,
        show_player_trajectories=True,
        show_court_trajectory=True,
        show_shuttlecock_trajectory=True,
        show_player_stats=True,
        show_performance_stats=False,
        save_images=False,
        language=config.language,
        output_dir=config.output_dir,
        ball_model_path=config.ball_model_path,
        template_path=config.template_path,
        pose_mode=config.pose_mode,
        pose_family=config.pose_family,
        yolo_pose_model=config.yolo_pose_model,
        show_pose_roi=config.show_pose_roi,
    )
    system.keep_audio = config.keep_audio
    system.calibration_path = config.calibration_path
    system.progress_callback = progress_callback
    system.cancel_callback = cancel_callback

    progress_callback({"stage": "processing", "progress": 5, "message": "Running video analysis"})
    system.process_video()

    if cancel_callback():
        raise RuntimeError("Analysis cancelled")

    progress_callback({"stage": "summarizing", "progress": 85, "message": "Writing session summary"})

    visualizer_summary = {}
    if config.visualize_positions:
        try:
            if config.language == "en":
                from .visualization.player_positions_en import analyze_player_positions
            else:
                from .visualization.player_positions_zh import analyze_player_positions

            visualizer_summary = analyze_player_positions(
                system.detections_path,
                os.path.join(system.save_dir, "position_visualizations"),
                fps=system.fps,
                include_summary=True,
            ) or {}
        except Exception as exc:
            warnings.append(f"Position visualization failed: {exc}")

    ended_at = time.time()
    summary = _build_summary(config, started_at, ended_at, system, warnings)
    if visualizer_summary:
        summary["stats"]["movement"] = visualizer_summary.get("movement_stats", {})
        summary["artifacts"].update(visualizer_summary.get("artifacts", {}))

    summary_path = os.path.join(config.output_dir, "session_summary.json")
    write_json(summary_path, summary)
    progress_callback({"stage": "completed", "progress": 100, "message": "Analysis completed", "summary_path": summary_path})
    return summary


def load_calibration(calibration_path: str) -> dict:
    with open(calibration_path, "r", encoding="utf-8") as file:
        return json.load(file)
