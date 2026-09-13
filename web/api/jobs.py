import asyncio
import json
import mimetypes
import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from badminton_analysis.service import AnalysisConfig, run_analysis

from .config import JOBS_DIR, RESULTS_DIR, UPLOADS_DIR
from .events import event_broker
from .models import JobConfig
from .repository import (
    get_job,
    list_artifacts,
    list_jobs,
    list_jobs_by_status,
    update_job,
    upsert_artifacts,
)
from .video_utils import extract_frame
from .compute_slot import lock as compute_lock


class JobManager:
    def __init__(self):
        self._current_job_id: str | None = None
        self._cancel_flags: dict[str, bool] = {}
        self._loop = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._queue_poller())
        self._loop.run_forever()

    async def _queue_poller(self):
        while True:
            await self._step_once()
            await asyncio.sleep(1)

    async def _step_once(self):
        with self._lock:
            if self._current_job_id:
                return
            queued_jobs = list_jobs_by_status("queued")
            if not queued_jobs:
                return
            if not compute_lock.acquire(blocking=False):
                return
            job = queued_jobs[0]
            self._current_job_id = job.id
            self._cancel_flags[job.id] = False
        try:
            await self._run_job(job.id)
        finally:
            compute_lock.release()

    async def _publish(self, job_id: str, payload: dict):
        payload.setdefault("timestamp", datetime.utcnow().isoformat())
        await event_broker.publish(job_id, payload)

    async def _run_job(self, job_id: str):
        job = get_job(job_id)
        update_job(job_id, status="running", started_at=datetime.utcnow().isoformat(), error_message=None)
        await self._publish(job_id, {"type": "status", "status": "running", "message": "Job started"})

        try:
            config = job.config_json
            template_path = job.template_frame_path
            calibration_path = str(Path(job.template_frame_path or "").parent / "calibration.json")
            analysis_config = AnalysisConfig(
                job_id=job.id,
                video_path=job.video_path,
                output_dir=job.output_dir,
                template_path=template_path,
                calibration_path=calibration_path,
                ball_model_path=config.ball_model_path,
                pose_family=config.pose_family,
                pose_mode=config.pose_mode,
                yolo_pose_model=config.yolo_pose_model,
                keep_audio=config.keep_audio,
                language=config.language,
                visualize_positions=config.visualize_positions,
                metadata={"job_name": job.name},
            )

            def progress_callback(payload: dict):
                if self._loop is not None:
                    asyncio.run_coroutine_threadsafe(
                        self._publish(job_id, {"type": "progress", **payload}),
                        self._loop,
                    )

            def cancel_callback() -> bool:
                return self._cancel_flags.get(job_id, False)

            summary = await asyncio.to_thread(run_analysis, analysis_config, progress_callback, cancel_callback)
            artifacts = {}
            for artifact_type, path in summary.get("artifacts", {}).items():
                if artifact_type.endswith("_dir"):
                    continue
                mime_type, _ = mimetypes.guess_type(path)
                artifacts[artifact_type] = (path, mime_type or "application/octet-stream")
            summary_path = os.path.join(job.output_dir, "session_summary.json")
            artifacts["summary"] = (summary_path, "application/json")
            upsert_artifacts(job_id, artifacts)
            update_job(job_id, status="succeeded", finished_at=datetime.utcnow().isoformat())
            await self._publish(job_id, {"type": "status", "status": "succeeded", "message": "Job finished", "summary": summary})
        except Exception as exc:
            update_job(job_id, status="failed", finished_at=datetime.utcnow().isoformat(), error_message=str(exc))
            await self._publish(job_id, {"type": "status", "status": "failed", "message": str(exc)})
        finally:
            with self._lock:
                self._current_job_id = None

    def queue_job(self, job_id: str) -> None:
        job = get_job(job_id)
        if job.status not in {"draft", "calibrating", "failed"}:
            raise RuntimeError(f"Cannot queue job in status {job.status}")
        update_job(job_id, status="queued", error_message=None)
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._publish(job_id, {"type": "status", "status": "queued", "message": "Job queued"}),
                self._loop,
            )

    def cancel_job(self, job_id: str) -> str:
        job = get_job(job_id)
        if job.status == "queued":
            update_job(job_id, status="cancelled", finished_at=datetime.utcnow().isoformat(), error_message="Cancelled by user")
            return "cancelled"
        if job.status == "running":
            self._cancel_flags[job_id] = True
            return "cancelling"
        raise RuntimeError(f"Cannot cancel job in status {job.status}")

    @property
    def current_job_id(self) -> str | None:
        return self._current_job_id


job_manager = JobManager()


def create_job_storage(job_id: str) -> tuple[str, str]:
    upload_dir = UPLOADS_DIR / job_id
    output_dir = RESULTS_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(upload_dir), str(output_dir)


def build_default_frame_path(job_id: str) -> str:
    return str(JOBS_DIR / job_id / "template_frame.jpg")


def ensure_job_workspace(job_id: str) -> Path:
    workspace = JOBS_DIR / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace
