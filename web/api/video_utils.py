import shutil
import subprocess
from pathlib import Path

import cv2


def probe_video(video_path: str) -> dict:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    duration = (total_frames / fps) if fps else 0
    return {
        "fps": fps,
        "total_frames": total_frames,
        "width": width,
        "height": height,
        "duration_sec": duration,
    }


def extract_frame(video_path: str, output_path: str, time_sec: float) -> str:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    frame_index = max(0, int(time_sec * fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    success, frame = capture.read()
    capture.release()
    if not success or frame is None:
        raise RuntimeError("Unable to extract video frame")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, frame)
    return output_path


def trim_video(input_path: str, output_path: str, start_sec: float, end_sec: float | None = None) -> str:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is required to trim video clips")
    if start_sec < 0:
        raise RuntimeError("Clip start time must be greater than or equal to 0")
    if end_sec is not None and end_sec <= start_sec:
        raise RuntimeError("Clip end time must be greater than clip start time")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_sec:.3f}",
    ]
    if end_sec is not None:
        command.extend(["-to", f"{end_sec:.3f}"])
    command.extend(
        [
            "-i",
            input_path,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            output_path,
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "FFmpeg trim failed"
        raise RuntimeError(message)
    return output_path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def disk_free_bytes(path: str) -> int:
    return shutil.disk_usage(path).free


def is_video_file(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm"}
