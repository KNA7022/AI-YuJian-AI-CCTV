import asyncio
import importlib.util
import json
import multiprocessing
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, SecretStr, field_validator

from badminton_analysis.live import live_worker
from badminton_analysis.media.frame_source import snapshot_worker
from . import compute_slot, live_store as store
from .config import ROOT_DIR
from .live_media import LiveMedia, exports, export_clip, playlist_duration, annotated_parts, annotated_ranges

router = APIRouter(prefix="/api/live", tags=["球场实时分析"])


class CourtConfig(BaseModel):
    name: str = Field(default="羽毛球场 1", min_length=1, max_length=80)
    rtsp_url: str = Field(default="rtsp://192.168.0.15/live/chn=0", max_length=2048)
    username: str = Field(default="admin", max_length=128)
    password: SecretStr | None = None
    pose_model: str = "weights/yolo11n-pose.pt"
    ball_model: str = "weights/yolo11s-ball.pt"
    ball_enabled: bool = False
    device: Literal["auto", "cpu", "cuda:0"] = "auto"
    analysis_fps: int = Field(default=10, ge=1, le=30)
    record_video: bool = True
    record_fps: int = Field(default=25, ge=1, le=60)
    max_duration_minutes: int = Field(default=120, ge=1, le=480)
    min_free_gb: float = Field(default=2, ge=0.5, le=100, allow_inf_nan=False)
    language: Literal["zh", "en"] = "zh"
    pose_family: Literal["yolo-pose", "rtmpose", "rtmo"] = "yolo-pose"
    pose_mode: Literal["lightweight", "balanced", "performance"] = "balanced"
    keep_audio: bool = True
    visualize_positions: bool = True
    auto_rallies: bool = True
    show_skeletons: bool = True
    show_player_trajectories: bool = True
    show_court_trajectory: bool = True
    show_shuttlecock_trajectory: bool = True
    show_player_stats: bool = True

    @field_validator("rtsp_url")
    @classmethod
    def valid_source(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "rtsp" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError("请填写不含账号密码的 RTSP 地址，凭据使用独立输入框。")
        if parsed.fragment or any(character.isspace() for character in value):
            raise ValueError("RTSP 地址不能含空格或片段标记。")
        _ = parsed.port
        return value


class Calibration(BaseModel):
    snapshot_id: str
    corners: list[tuple[int, int]] = Field(min_length=4, max_length=4)


def validate_corners(corners, width, height):
    if len(set(map(tuple, corners))) != 4 or any(not (0 <= x < width and 0 <= y < height) for x, y in corners):
        raise ValueError("角点不能重复或超出图像边界。")
    turns = []
    for i in range(4):
        a, b, c = corners[i], corners[(i+1) % 4], corners[(i+2) % 4]
        turns.append((b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]))
    area = sum(corners[i][0]*corners[(i+1)%4][1]-corners[(i+1)%4][0]*corners[i][1] for i in range(4)) / 2
    if min(turns) <= 0 or area < width*height*0.005:
        raise ValueError("请按左上、右上、右下、左下标记有效的凸四边形。")
    a, b, c, d = corners
    if not (a[0] < b[0] and d[0] < c[0] and a[1]+b[1] < c[1]+d[1]):
        raise ValueError("角点顺序错误，请从左上角开始。")


def public_court(court):
    if court is None:
        return None
    return {**CourtConfig().model_dump(exclude={"password"}), **{key: value for key, value in court.items() if key != "password"},
            "has_password": bool(court.get("password"))}


def source_url(court):
    parsed = urlsplit(court["rtsp_url"])
    userinfo = ""
    if court.get("username"):
        userinfo = quote(court["username"], safe="") + ":" + quote(court.get("password", ""), safe="") + "@"
    return urlunsplit((parsed.scheme, userinfo + parsed.netloc, parsed.path, parsed.query, ""))


def model_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def prerequisites(court):
    missing = [name for name in ("cv2", "ultralytics", "torch") if importlib.util.find_spec(name) is None]
    errors = ["缺少运行依赖：" + ", ".join(missing)] if missing else []
    if not court:
        return errors + ["请先保存摄像头配置。"]
    if not court.get("calibration"):
        errors.append("请先抓取摄像头画面并完成四点标定。")
    if court.get("pose_family", "yolo-pose") != "yolo-pose":
        for name in ("rtmlib", "onnxruntime"):
            if importlib.util.find_spec(name) is None:
                errors.append(f"缺少姿态运行依赖：{name}")
        mode = court.get("pose_mode", "balanced")
        family = court["pose_family"]
        tier = ({"lightweight":"t", "balanced":"s", "performance":"m"} if family == "rtmpose" else
                {"lightweight":"s", "balanced":"m", "performance":"l"})[mode]
        if not list((ROOT_DIR/"weights").glob(f"{family}-{tier}_*.onnx")) or (
                family == "rtmpose" and not (ROOT_DIR/"weights/yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx").exists()):
            errors.append("缺少所选档位的 ONNX 权重，请运行模型下载脚本。")
    for field in (["pose_model"] if court.get("pose_family", "yolo-pose") == "yolo-pose" else []) + (["ball_model"] if court["ball_enabled"] else []):
        if not model_path(court[field]).is_file():
            errors.append("缺少人物姿态模型。" if field == "pose_model" else "缺少羽毛球模型，请准备权重或关闭羽毛球检测。")
    if shutil.disk_usage(store.LIVE_RESULTS).free < court["min_free_gb"] * 1024**3:
        errors.append("可用磁盘空间低于配置的保留空间。")
    return errors


class LiveManager:
    def __init__(self):
        self.guard = threading.RLock()
        self.process = None
        self.session_id = None
        self.stop_event = None
        self.preview = None
        self.preview_time = 0.0
        self.monitor = None
        self.media = None

    def ensure_idle(self):
        if self.session_id is not None:
            raise HTTPException(409, "请先停止当前直播会话。")

    def start(self, court):
        court = {**CourtConfig().model_dump(exclude={"password"}), **court}
        with self.guard:
            self.ensure_idle()
            if not compute_slot.lock.acquire(blocking=False):
                raise HTTPException(409, "已有分析任务正在运行，请等待结束后开始直播。")
            context = multiprocessing.get_context("spawn")
            session_id = uuid.uuid4().hex
            output = store.LIVE_RESULTS / session_id
            try:
                output.mkdir(parents=True)
                store.create_session(session_id, {"name": court["name"], "message": "正在初始化模型。", "stats": {},
                                                  "calibration_version": court["calibration"]["version"], "rallies": []})
                config = {**court, "rtsp_url": source_url(court),
                          "pose_model": str(model_path(court["pose_model"])), "ball_model": str(model_path(court["ball_model"]))}
                config.pop("password", None)
                self.stop_event = context.Event()
                events = context.Queue(maxsize=4)
                self.process = context.Process(target=live_worker, args=(config, str(output), self.stop_event, events), daemon=True)
                self.session_id = session_id
                self.preview = None
                self.media = LiveMedia(source_url(court), output, court["keep_audio"], court["record_video"])
                if court["record_video"] or court["keep_audio"]:
                    self.media.start()
                self.process.start()
                self.monitor = threading.Thread(target=self._watch, args=(session_id, events, output), daemon=True)
                self.monitor.start()
                return store.get_session(session_id)
            except Exception:
                if self.media:
                    self.media.close()
                if self.process and self.process.is_alive():
                    self.process.terminate()
                    self.process.join(5)
                self.session_id = None
                compute_slot.lock.release()
                try:
                    store.update_session(session_id, status="failed", message="无法启动分析进程。")
                except KeyError:
                    pass
                raise

    def _watch(self, session_id, events, output):
        process = self.process
        last_heartbeat = time.monotonic()
        stop_started = None
        last_media = 0
        try:
            while process.is_alive():
                if self.media and time.monotonic()-last_media > 2:
                    store.update_session(session_id, media=self.media.poll())
                    last_media = time.monotonic()
                try:
                    event = events.get(timeout=0.5)
                except queue.Empty:
                    event = None
                if event:
                    last_heartbeat = time.monotonic()
                    preview = event.pop("preview", None)
                    with self.guard:
                        if preview:
                            self.preview = preview
                            self.preview_time = time.monotonic()
                        if self.stop_event.is_set():
                            event.pop("status", None)
                        store.update_session(session_id, **event)
                if self.stop_event.is_set():
                    stop_started = stop_started or time.monotonic()
                if (stop_started and time.monotonic()-stop_started > 20) or time.monotonic()-last_heartbeat > 120:
                    process.terminate()
                    break
            process.join(5)
            summary_file = output / "session_summary.json"
            if summary_file.exists():
                summary = json.loads(summary_file.read_text(encoding="utf-8"))
            else:
                summary = {"status": "interrupted", "message": "分析进程意外中断，已封存分片仍可下载。"}
            with self.guard:
                store.update_session(session_id, **summary)
        finally:
            if self.media:
                self.media.close()
                store.update_session(session_id, media={"ready": playlist_duration(output/"source.m3u8") > 0,
                    "has_audio": getattr(self.media, "has_audio", False), "keep_audio": getattr(self.media, "keep_audio", False),
                    "duration_sec": playlist_duration(output/"source.m3u8"), "running": False,
                    "archive": getattr(self.media, "archive", True), "annotated_ranges": annotated_ranges(output)})
            if process.is_alive():
                process.kill()
                process.join(5)
            events.close()
            with self.guard:
                self.session_id = None
                self.preview = None
                compute_slot.lock.release()

    def stop(self, session_id):
        with self.guard:
            session = get_session_or_404(session_id)
            if self.session_id != session_id:
                return session
            store.update_session(session_id, status="stopping", message="正在停止取流并封存录像。")
            self.stop_event.set()
            return store.get_session(session_id)

    def shutdown(self):
        if self.session_id:
            self.stop(self.session_id)
        if self.monitor:
            self.monitor.join(27)


manager = LiveManager()


def get_session_or_404(session_id):
    try:
        return store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(404, "会话不存在。") from exc


@router.get("/court")
def read_court():
    return public_court(store.get_court())


@router.put("/court")
def configure_court(payload: CourtConfig):
    with manager.guard:
        manager.ensure_idle()
        previous = store.get_court() or {}
        court = payload.model_dump(exclude={"password"})
        court["password"] = payload.password.get_secret_value() if payload.password is not None else previous.get("password", "")
        same_source = all(court.get(key) == previous.get(key) for key in ("rtsp_url", "username", "password"))
        for key in ("calibration", "snapshot"):
            court[key] = previous.get(key) if same_source else None
        store.save_court(court)
        return public_court(court)


@router.post("/court/snapshot")
def capture_snapshot():
    with manager.guard:
        manager.ensure_idle()
        court = store.get_court()
        if not court:
            raise HTTPException(400, "请先保存摄像头配置。")
        if importlib.util.find_spec("cv2") is None:
            raise HTTPException(503, "缺少 OpenCV，请安装运行依赖。")
        snapshot_id = uuid.uuid4().hex
        destination = store.PRIVATE_DIR / f"snapshot_{snapshot_id}.jpg"
        context = multiprocessing.get_context("spawn")
        result = context.Queue(maxsize=1)
        process = context.Process(target=snapshot_worker, args=(source_url(court), str(destination), result), daemon=True)
        try:
            process.start()
            try:
                info = result.get(timeout=18)
            except queue.Empty:
                raise HTTPException(504, "摄像头连接超时，请检查网络、地址和账号。")
            if "error" in info:
                raise HTTPException(502, info["error"])
            court["snapshot"] = {**info, "id": snapshot_id, "captured_at": store.now()}
            store.save_court(court)
            return public_court(court)
        finally:
            process.join(1)
            if process.is_alive():
                process.terminate()
                process.join(3)
            result.close()


@router.get("/court/snapshot.jpg")
def snapshot_image():
    court = store.get_court()
    snapshot = court.get("snapshot") if court else None
    if not snapshot:
        raise HTTPException(404, "尚未抓取画面。")
    return FileResponse(store.PRIVATE_DIR / f"snapshot_{snapshot['id']}.jpg", media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.put("/court/calibration")
def calibrate(payload: Calibration):
    with manager.guard:
        manager.ensure_idle()
        court = store.get_court()
        snapshot = court.get("snapshot") if court else None
        if not snapshot or snapshot["id"] != payload.snapshot_id:
            raise HTTPException(409, "参考画面已变化，请刷新后重新标定。")
        try:
            validate_corners(payload.corners, snapshot["width"], snapshot["height"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        court["calibration"] = {"version": uuid.uuid4().hex, "corners": payload.corners,
                                "width": snapshot["width"], "height": snapshot["height"],
                                "snapshot_id": snapshot["id"], "created_at": store.now()}
        store.save_court(court)
        return public_court(court)


@router.get("/health")
def health():
    court = store.get_court()
    return {"errors": prerequisites(court), "active_session_id": manager.session_id,
            "disk_free_gb": round(shutil.disk_usage(store.LIVE_RESULTS).free/1024**3, 2),
            "mode": "singles", "ball_enabled": bool(court and court["ball_enabled"])}


@router.post("/sessions")
def start_session():
    with manager.guard:
        court = store.get_court()
        errors = prerequisites(court)
        if errors:
            raise HTTPException(409, "；".join(errors))
        return manager.start(court)


@router.get("/sessions")
def list_sessions():
    return store.list_sessions()


@router.get("/sessions/{session_id}")
def session_details(session_id: str):
    return get_session_or_404(session_id)


@router.post("/sessions/{session_id}/stop")
def stop_session(session_id: str):
    return manager.stop(session_id)


@router.post("/sessions/{session_id}/rallies")
def mark_rally(session_id: str):
    with manager.guard:
        session = get_session_or_404(session_id)
        if session_id != manager.session_id or session["status"] != "running":
            raise HTTPException(409, "仅可在运行时标记回合边界。")
        rallies = session.get("rallies", []) + [{"time_sec": session.get("elapsed_sec", 0), "marked_at": store.now()}]
        (store.LIVE_RESULTS / session_id / "rallies.json").write_text(json.dumps(rallies, ensure_ascii=False), encoding="utf-8")
        return store.update_session(session_id, rallies=rallies)


@router.get("/sessions/{session_id}/preview")
async def preview(session_id: str):
    get_session_or_404(session_id)
    if manager.session_id != session_id:
        raise HTTPException(409, "会话未运行。")

    async def frames():
        last = 0.0
        while manager.session_id == session_id:
            if manager.preview and manager.preview_time != last and time.monotonic()-manager.preview_time < 3:
                last = manager.preview_time
                frame = manager.preview
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.2)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store"})


@router.get("/sessions/{session_id}/artifacts")
def artifacts(session_id: str):
    session = get_session_or_404(session_id)
    directory = store.LIVE_RESULTS / session_id
    # Never offer a video whose writer has not closed it yet.
    closed = set()
    for index in directory.glob("*_index.json"):
        try:
            closed.update(item["file"] for item in json.loads(index.read_text(encoding="utf-8")) if item["closed"])
        except (OSError, ValueError):
            continue
    completed_clips = {path.with_suffix(".mp4").name for path in directory.glob("clip_*.json")
                       if json.loads(path.read_text(encoding="utf-8")).get("status") == "completed"}
    return [{"name": path.name, "size": path.stat().st_size,
             "url": f"/api/live/sessions/{session_id}/artifacts/{path.name}"}
            for path in sorted(directory.glob("*")) if path.is_file() and path.suffix in {".json", ".jsonl", ".jpg", ".mp4"}
            and (path.suffix != ".mp4" or path.name in closed or path.name in completed_clips)
            and (path.suffix != ".jsonl" or session["status"] not in store.ACTIVE)]


@router.get("/sessions/{session_id}/artifacts/{filename}")
def download_artifact(session_id: str, filename: str):
    allowed = {item["name"] for item in artifacts(session_id)}
    if filename not in allowed:
        raise HTTPException(404, "文件不存在或尚未封存。")
    return FileResponse(store.LIVE_RESULTS / session_id / filename, filename=filename)


@router.get("/sessions/{session_id}/images/{filename}")
def chart_image(session_id: str, filename: str):
    get_session_or_404(session_id)
    allowed = {f"{scope}_{kind}.jpg" for scope in ("match", "rally") for kind in ("heatmap", "scatter")}
    path = store.LIVE_RESULTS/session_id/filename
    if filename not in allowed or not path.is_file():
        raise HTTPException(404, "图表正在生成。")
    return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/sessions/{session_id}/media/{filename}")
def source_media(session_id: str, filename: str):
    get_session_or_404(session_id)
    import re
    if filename != "source.m3u8" and not re.fullmatch(r"source_\d+\.ts", filename):
        raise HTTPException(404, "音视频分片不存在。")
    path = store.LIVE_RESULTS/session_id/filename
    if not path.is_file():
        raise HTTPException(404, "音视频仍在缓冲。")
    if filename.endswith("m3u8"):
        return Response(path.read_bytes(), media_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-store"})
    return FileResponse(path, media_type="video/mp2t", headers={"Cache-Control": "no-store"})


class ClipRequest(BaseModel):
    kind: Literal["original", "annotated"] = "original"
    start_sec: float = Field(ge=0, allow_inf_nan=False)
    end_sec: float = Field(gt=0, allow_inf_nan=False)


@router.post("/sessions/{session_id}/clips")
def create_clip(session_id: str, payload: ClipRequest):
    session = get_session_or_404(session_id)
    if session.get("media", {}).get("archive") is False:
        raise HTTPException(409, "启用录像保存后才可导出历史片段。")
    directory = store.LIVE_RESULTS/session_id
    duration = playlist_duration(directory/"source.m3u8")
    if not 0 < payload.end_sec-payload.start_sec <= 600 or (payload.kind == "original" and payload.end_sec > duration):
        raise HTTPException(422, "请选择已接收范围内不超过 10 分钟的片段。")
    if payload.kind == "annotated":
        try:
            annotated_parts(directory, payload.start_sec, payload.end_sec)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    with manager.guard:
        for path in directory.glob("clip_*.json"):
            if json.loads(path.read_text(encoding="utf-8")).get("status") in {"queued", "running"}:
                raise HTTPException(409, "已有片段正在导出，请稍后重试。")
        clip_id = uuid.uuid4().hex
        (directory/f"clip_{clip_id}.json").write_text(json.dumps({"status":"queued", "id":clip_id}), encoding="utf-8")
        exports.submit(export_clip, directory, clip_id, payload.start_sec, payload.end_sec, payload.kind)
    return {"id": clip_id, "status":"queued"}


@router.get("/sessions/{session_id}/detections")
def detection_snapshot(session_id: str):
    get_session_or_404(session_id)
    path = store.LIVE_RESULTS/session_id/"detections.jsonl"
    if not path.exists():
        raise HTTPException(404, "尚无检测数据。")
    size = path.stat().st_size
    def lines():
        with path.open("rb") as stream:
            remaining = size
            while remaining:
                line = stream.readline(remaining)
                if not line or not line.endswith(b"\n"):
                    break
                remaining -= len(line)
                yield line
    return StreamingResponse(lines(), media_type="application/x-ndjson",
                             headers={"Content-Disposition": 'attachment; filename="detections-snapshot.jsonl"'})


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    with manager.guard:
        session = get_session_or_404(session_id)
        if session_id == manager.session_id or session["status"] in store.ACTIVE:
            raise HTTPException(409, "请先停止会话再删除。")
        directory = (store.LIVE_RESULTS/session_id).resolve()
        if directory.parent != store.LIVE_RESULTS.resolve():
            raise HTTPException(400, "无效会话路径。")
        for path in directory.glob("clip_*.json"):
            if json.loads(path.read_text(encoding="utf-8")).get("status") in {"queued", "running"}:
                raise HTTPException(409, "请等待片段导出完成后删除。")
        if directory.exists():
            shutil.rmtree(directory)
        with store.connection() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    return {"deleted": True}
