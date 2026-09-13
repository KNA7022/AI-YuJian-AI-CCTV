import json
import os
import shutil
import uuid
import base64
import hmac
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import FRONTEND_DIST_DIR, JOBS_DIR, RESULTS_DIR, STORAGE_DIR, UPLOADS_DIR
from .db import init_db
from .jobs import (
    build_default_frame_path,
    create_job_storage,
    ensure_job_workspace,
    job_manager,
)
from .models import CalibrationPayload, JobConfig, StartJobResponse, SystemHealth
from .repository import create_job, delete_job_records, get_job, list_artifacts, list_jobs, update_job
from .video_utils import disk_free_bytes, extract_frame, ffmpeg_available, is_video_file, probe_video, trim_video
from .live_api import router as live_router, manager as live_manager
from .live_store import init_live_db, recover_sessions


app = FastAPI(title="Good Badminton Web Demo")
app.include_router(live_router)


@app.middleware("http")
async def operator_access(request, call_next):
    password = os.environ.get("YUJIAN_PASSWORD")
    if password:
        try:
            scheme, value = request.headers.get("authorization", "").split(" ", 1)
            credentials = base64.b64decode(value, validate=True).decode("utf-8")
            valid = scheme.lower() == "basic" and hmac.compare_digest(credentials.encode(), ("operator:" + password).encode())
        except (ValueError, UnicodeError):
            valid = False
        if not valid:
            return JSONResponse({"detail": "请使用 operator 账号登录。"}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="YuJian", charset="UTF-8"'})
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    # Pydantic's default error includes submitted inputs, including camera secrets.
    messages = [f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "；".join(messages)})
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("YUJIAN_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    init_db()
    init_live_db()
    recover_sessions()
    for job in list_jobs():
        if job.status == "running":
            update_job(job.id, status="failed", error_message="Marked failed after restart")
    job_manager.start()


@app.on_event("shutdown")
async def on_shutdown():
    import asyncio
    await asyncio.to_thread(live_manager.shutdown)


def _parse_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _parse_optional_time(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    normalized = value.strip()
    if ":" in normalized:
        parts = normalized.split(":")
        if len(parts) > 3:
            raise HTTPException(status_code=400, detail="Clip time must be seconds, mm:ss, or hh:mm:ss")
        try:
            total = 0.0
            for part in parts:
                total = total * 60 + float(part)
            return total
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Clip time must be seconds, mm:ss, or hh:mm:ss") from exc
    try:
        return float(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Clip time must be seconds, mm:ss, or hh:mm:ss") from exc


@app.post("/api/jobs")
async def create_job_endpoint(
    file: UploadFile = File(...),
    name: str = Form(...),
    language: str = Form("zh"),
    pose_family: str = Form("rtmpose"),
    pose_mode: str = Form("balanced"),
    yolo_pose_model: str = Form("yolo11n-pose.pt"),
    keep_audio: str = Form("true"),
    visualize_positions: str = Form("true"),
    ball_model_path: str = Form("weights/yolo11s-ball.pt"),
    trim_enabled: str = Form("false"),
    trim_start_sec: str = Form(""),
    trim_end_sec: str = Form(""),
):
    if not is_video_file(file.filename or ""):
        raise HTTPException(status_code=400, detail="Only video files are supported")

    job_id = uuid.uuid4().hex
    upload_dir, output_dir = create_job_storage(job_id)
    ensure_job_workspace(job_id)
    safe_name = Path(file.filename or "upload.mp4").name
    video_path = Path(upload_dir) / safe_name

    with video_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        original_video_info = probe_video(str(video_path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source_video_path = video_path
    video_info = original_video_info
    clip_info: dict | None = None
    if _parse_bool(trim_enabled, False):
        start_sec = _parse_optional_time(trim_start_sec) or 0.0
        end_sec = _parse_optional_time(trim_end_sec)
        if end_sec is not None and end_sec > original_video_info["duration_sec"]:
            raise HTTPException(status_code=400, detail="Clip end time cannot exceed video duration")
        if start_sec >= original_video_info["duration_sec"]:
            raise HTTPException(status_code=400, detail="Clip start time must be before the end of the video")
        clip_path = Path(upload_dir) / f"clip_{safe_name}"
        try:
            trim_video(str(video_path), str(clip_path), start_sec, end_sec)
            video_info = probe_video(str(clip_path))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Video clip failed: {exc}") from exc
        source_video_path = clip_path
        clip_info = {
            "enabled": True,
            "source_path": str(video_path),
            "video_path": str(clip_path),
            "start_sec": start_sec,
            "end_sec": end_sec,
            "original_duration_sec": original_video_info["duration_sec"],
            "duration_sec": video_info["duration_sec"],
        }

    config = JobConfig(
        language=language,
        pose_family=pose_family,
        pose_mode=pose_mode,
        yolo_pose_model=yolo_pose_model,
        keep_audio=_parse_bool(keep_audio, True),
        visualize_positions=_parse_bool(visualize_positions, True),
        ball_model_path=ball_model_path,
        trim_enabled=clip_info is not None,
        trim_start_sec=clip_info["start_sec"] if clip_info else None,
        trim_end_sec=clip_info["end_sec"] if clip_info else None,
    )
    job = create_job(job_id, name, str(source_video_path), output_dir, config)
    workspace = ensure_job_workspace(job_id)
    template_frame_path = workspace / "template_frame.jpg"
    extract_frame(str(source_video_path), str(template_frame_path), 0)
    job = update_job(job_id, template_frame_path=str(template_frame_path), status="calibrating")
    return {"job_id": job.id, "status": job.status, "video": video_info, "original_video": original_video_info, "clip": clip_info}


@app.get("/api/jobs")
async def list_jobs_endpoint():
    return [job.model_dump(mode="json") for job in list_jobs()]


@app.get("/api/jobs/{job_id}")
async def get_job_endpoint(job_id: str):
    try:
        job = get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    artifacts = [artifact.model_dump(mode="json") for artifact in list_artifacts(job_id)]
    response = job.model_dump(mode="json")
    response["artifacts"] = artifacts
    summary_path = Path(job.output_dir) / "session_summary.json"
    if summary_path.exists():
        response["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
    return response


@app.post("/api/jobs/{job_id}/calibration")
async def save_calibration_endpoint(job_id: str, payload: CalibrationPayload):
    try:
        job = get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    if len(payload.corners) != 4:
        raise HTTPException(status_code=400, detail="Exactly four court corners are required")

    workspace = ensure_job_workspace(job_id)
    template_frame_path = workspace / "template_frame.jpg"
    extract_frame(job.video_path, str(template_frame_path), payload.frame_time_sec)
    calibration_path = workspace / "calibration.json"
    calibration = {
        "frame_time_sec": payload.frame_time_sec,
        "corners": payload.corners,
        "template_frame_path": str(template_frame_path),
    }
    calibration_path.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
    updated_job = update_job(
        job_id,
        status="calibrating",
        template_frame_path=str(template_frame_path),
        calibration_points=payload.corners,
    )
    return {"job": updated_job.model_dump(mode="json"), "calibration_path": str(calibration_path)}


@app.post("/api/jobs/{job_id}/start", response_model=StartJobResponse)
async def start_job_endpoint(job_id: str):
    try:
        job = get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    if not job.template_frame_path or not job.calibration_points:
        raise HTTPException(status_code=400, detail="Calibration must be completed before starting analysis")
    try:
        job_manager.queue_job(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = get_job(job_id)
    return StartJobResponse(job_id=updated.id, status=updated.status)


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    try:
        result = job_manager.cancel_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id, "status": result}


def _safe_rmtree(path: Path, allowed_parent: Path) -> None:
    resolved_path = path.resolve()
    resolved_parent = allowed_parent.resolve()
    if resolved_path == resolved_parent or resolved_parent not in resolved_path.parents:
        raise RuntimeError(f"Refusing to delete unsafe path: {path}")
    if resolved_path.exists():
        shutil.rmtree(resolved_path)


@app.delete("/api/jobs/{job_id}")
async def delete_job_endpoint(job_id: str):
    try:
        job = get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    if job.status == "running" or job_manager.current_job_id == job_id:
        raise HTTPException(status_code=400, detail="Running jobs cannot be deleted. Cancel or wait for completion first.")

    delete_job_records(job_id)
    for path, parent in [
        (UPLOADS_DIR / job_id, UPLOADS_DIR),
        (JOBS_DIR / job_id, JOBS_DIR),
        (RESULTS_DIR / job_id, RESULTS_DIR),
    ]:
        _safe_rmtree(path, parent)
    return {"job_id": job_id, "deleted": True}


@app.get("/api/jobs/{job_id}/events")
async def job_events_endpoint(job_id: str):
    from .events import event_broker

    async def event_stream():
        yield "event: connected\ndata: {}\n\n"
        async for payload in event_broker.subscribe(job_id):
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/artifacts/{artifact_type}")
async def artifact_endpoint(job_id: str, artifact_type: str, download: bool = Query(False)):
    artifacts = {artifact.type: artifact for artifact in list_artifacts(job_id)}
    artifact = artifacts.get(artifact_type)
    if artifact is None or not os.path.exists(artifact.path):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(
        artifact.path,
        media_type=artifact.mime_type,
        filename=os.path.basename(artifact.path),
        content_disposition_type="attachment" if download else "inline",
    )


@app.get("/api/system/health", response_model=SystemHealth)
async def health_endpoint():
    jobs = list_jobs()
    queued_jobs = len([job for job in jobs if job.status == "queued"])
    return SystemHealth(
        ffmpeg_available=ffmpeg_available(),
        disk_free_bytes=disk_free_bytes(str(STORAGE_DIR)),
        queued_jobs=queued_jobs,
        running_job_id=job_manager.current_job_id,
    )


app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")
app.mount("/results", StaticFiles(directory=RESULTS_DIR), name="results")

if FRONTEND_DIST_DIR.exists():
    class FrontendFiles(StaticFiles):
        async def get_response(self, path, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if exc.status_code == 404 and (path in {"live", "history"} or path.startswith("jobs/")):
                    return await super().get_response("index.html", scope)
                raise

    app.mount("/", FrontendFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
