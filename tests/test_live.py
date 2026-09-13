import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from badminton_analysis.live import SegmentWriter
from badminton_analysis.live_stats import MovementStats
from badminton_analysis.media.frame_source import FramePacket, LatestFrameSource
from web.api import live_api, live_store
from badminton_analysis.live_features import LiveAnalytics, RallyTracker
from web.api.live_media import annotated_parts, export_clip
from badminton_analysis.media.files import replace_when_ready


def test_atomic_publish_retries_transient_windows_reader(tmp_path, monkeypatch):
    source, target = tmp_path/'new.tmp', tmp_path/'status.json'
    source.write_text('new', encoding='utf-8')
    target.write_text('old', encoding='utf-8')
    original = Path.replace
    attempts = []
    def locked_replace(path, destination):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError('reader holds file')
        return original(path, destination)
    monkeypatch.setattr(Path, 'replace', locked_replace)
    replace_when_ready(source, target)
    assert target.read_text(encoding='utf-8') == 'new' and len(attempts) == 3


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(live_store, "PRIVATE_DIR", tmp_path / "private")
    monkeypatch.setattr(live_store, "LIVE_RESULTS", tmp_path / "results")
    monkeypatch.setattr(live_api, "manager", live_api.LiveManager())
    class NoMedia:
        def __init__(self, *args): pass
        def start(self): pass
        def close(self): pass
        def poll(self): return {"ready": False}
    monkeypatch.setattr(live_api, "LiveMedia", NoMedia)
    live_store.init_live_db()
    app = FastAPI()
    app.include_router(live_api.router)
    with TestClient(app) as client:
        yield client


def test_password_is_not_returned_and_blank_update_preserves_it(client):
    response = client.put("/api/live/court", json={"password": "my-private-secret"})
    assert response.status_code == 200
    assert "my-private-secret" not in response.text
    assert response.json()["has_password"]
    client.put("/api/live/court", json={"name": "更名球场"})
    assert live_store.get_court()["password"] == "my-private-secret"
    assert "my-private-secret" not in client.get("/api/live/court").text


def test_credentials_are_url_encoded():
    url = live_api.source_url({"rtsp_url": "rtsp://192.168.0.15/live/chn=0", "username": "a@b", "password": "x:/?#"})
    assert url == "rtsp://a%40b:x%3A%2F%3F%23@192.168.0.15/live/chn=0"


def test_live_rally_motion_stationary_and_manual_reset(tmp_path):
    tracker = RallyTracker()
    for index in range(10):
        tracker.update(index*.1, (index*5, 20))
    assert tracker.active and tracker.count == 1
    tracker.update(3.5, (45, 20))
    assert not tracker.active and len(tracker.intervals) == 1
    analytics = LiveAnalytics(False)
    for index in range(6):
        analytics.update({"upper": {"court": [1+index*.1, 2]}, "lower": {"court": None}}, index*.1, None, manual=index == 0)
    assert analytics.stats()["upper"]["rally_distance"] == pytest.approx(.5)
    analytics.update({"upper": {"court": [1.6, 2]}, "lower": {"court": None}}, .6, None, manual=True)
    assert analytics.stats()["upper"]["rally_distance"] == 0
    assert analytics.stats()["upper"]["match_distance"] == pytest.approx(.6)
    analytics.write_charts(tmp_path)
    assert len(list(tmp_path.glob("*.jpg"))) == 4  # Charts exist before session end.
    assert analytics.grids["rally"]["upper"].sum() == 1


def test_live_snapshot_clips_and_delete_guards(client, monkeypatch):
    session_id = "live-features-test"
    live_store.create_session(session_id, {"name": "test"})
    directory = live_store.LIVE_RESULTS/session_id
    directory.mkdir()
    (directory/"detections.jsonl").write_bytes(b'{"frame":1}\n{"frame":2')
    response = client.get(f"/api/live/sessions/{session_id}/detections")
    assert response.content == b'{"frame":1}\n'
    assert client.delete(f"/api/live/sessions/{session_id}").status_code == 409
    (directory/"annotated_index.json").write_text(json.dumps([
        {"file":"annotated_0000.mp4", "start_sec":2, "frames":20, "fps":10, "closed":True},
        {"file":"annotated_0001.mp4", "start_sec":6, "frames":20, "fps":10, "closed":True}]), encoding="utf-8")
    with pytest.raises(ValueError):
        annotated_parts(directory, 3, 7)  # A disconnect cannot silently shorten a clip.
    assert client.post(f"/api/live/sessions/{session_id}/clips", json={"kind":"annotated", "start_sec":3,"end_sec":7}).status_code == 422
    submitted = []
    monkeypatch.setattr(live_api.exports, "submit", lambda *args: submitted.append(args))
    assert client.post(f"/api/live/sessions/{session_id}/clips", json={"kind":"annotated", "start_sec":2.5,"end_sec":3.5}).status_code == 200
    assert submitted[0][-1] == "annotated"
    live_store.update_session(session_id, status="stopped")
    assert client.delete(f"/api/live/sessions/{session_id}").status_code == 409  # Export is queued.
    for path in directory.glob("clip_*.json"):
        path.write_text('{"status":"failed"}', encoding="utf-8")
    assert client.delete(f"/api/live/sessions/{session_id}").status_code == 200
    assert not directory.exists()


def test_annotated_export_preserves_audio_and_duration(tmp_path):
    import cv2
    import subprocess
    from datetime import datetime
    from badminton_analysis.media.binaries import ffmpeg_binary
    ffmpeg = ffmpeg_binary()
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:r=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "5", "-c:v", "libx264", "-g", "10",
                    "-c:a", "aac", "-f", "hls", "-hls_time", "1", "-hls_flags", "program_date_time",
                    str(tmp_path/"source.m3u8")], check=True, capture_output=True, timeout=30)
    manifest = (tmp_path/"source.m3u8").read_text(encoding="utf-8")
    date = next(line.split(":",1)[1] for line in manifest.splitlines() if line.startswith("#EXT-X-PROGRAM-DATE-TIME:"))
    (tmp_path/"metadata.json").write_text(json.dumps({"audio":True,"started_at_unix":datetime.fromisoformat(date).timestamp()}), encoding="utf-8")
    writer = SegmentWriter(tmp_path, "annotated", fps=10, seconds=2)
    for index in range(40):
        writer.write(np.full((120,160,3), (0, 0, 255), dtype=np.uint8), index/10, 1)
    writer.close_segment()
    export_clip(tmp_path, "annotated-test", 1, 3, "annotated")
    state = json.loads((tmp_path/"clip_annotated-test.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed", state
    cap = cv2.VideoCapture(str(tmp_path/"clip_annotated-test.mp4"))
    assert cap.get(cv2.CAP_PROP_FRAME_COUNT)/cap.get(cv2.CAP_PROP_FPS) == pytest.approx(2, abs=.15)
    ok, frame = cap.read()
    cap.release()
    assert ok and frame[:,:,2].mean() > 200  # Uses annotated red frames, not blue source.
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(tmp_path/"clip_annotated-test.mp4"), "-map", "0:a:0", "-f", "null", "-"], capture_output=True, timeout=20)
    assert result.returncode == 0  # Audio stream exists and decodes.


@pytest.mark.parametrize("url", ["file:///secret", "http://example.org", "rtsp://user:secret@host/a", "rtsp:///missing"])
def test_non_rtsp_and_embedded_credentials_rejected(client, url):
    assert client.put("/api/live/court", json={"rtsp_url": url}).status_code == 422


def test_start_requires_calibration_and_models(client):
    client.put("/api/live/court", json={"pose_model": "weights/missing-test.pt"})
    response = client.post("/api/live/sessions")
    assert response.status_code == 409
    assert "标定" in response.text and "模型" in response.text
    assert live_api.manager.session_id is None


def test_calibration_version_and_invalidation(client):
    client.put("/api/live/court", json={})
    court = live_store.get_court()
    court["snapshot"] = {"id": "test-image", "width": 640, "height": 480}
    live_store.save_court(court)
    corners = [[100, 50], [500, 50], [580, 420], [40, 420]]
    assert client.put("/api/live/court/calibration", json={"snapshot_id": "stale", "corners": corners}).status_code == 409
    response = client.put("/api/live/court/calibration", json={"snapshot_id": "test-image", "corners": corners})
    assert response.status_code == 200
    assert response.json()["calibration"]["width"] == 640
    version = response.json()["calibration"]["version"]
    assert client.put("/api/live/court", json={"name": "新名字"}).json()["calibration"]["version"] == version
    response = client.put("/api/live/court", json={"rtsp_url": "rtsp://192.168.0.16/live/chn=0"})
    assert response.json()["calibration"] is None
    assert response.json()["snapshot"] is None


@pytest.mark.parametrize("corners", [
    [[1, 1], [1, 1], [20, 20], [1, 20]],
    [[0, 0], [640, 0], [639, 400], [0, 400]],
    [[0, 0], [600, 400], [600, 0], [0, 400]],
    [[0, 0], [0, 400], [600, 400], [600, 0]],
])
def test_invalid_geometry(corners):
    with pytest.raises(ValueError):
        live_api.validate_corners(corners, 640, 480)


def test_stats_are_idempotent_and_use_elapsed_time():
    stats = MovementStats()
    stats.update("upper", [1, 1], 0)
    stats.update("upper", [2, 1], 0.5)
    first = stats.snapshot()
    assert first["upper"]["distance_m"] == 1
    assert first["upper"]["speed_mps"] == 2
    assert stats.snapshot() == first
    stats.update("upper", [2, 1], 0.5)
    assert stats.snapshot()["upper"]["distance_m"] == 1
    stats.update("upper", None, 0.6)
    stats.update("upper", [5, 1], 0.7)
    assert stats.snapshot()["upper"]["distance_m"] == 1
    stats.reset_continuity()
    stats.update("upper", [0, 1], 0.8)
    assert stats.snapshot()["upper"]["distance_m"] == 1


def test_stats_reject_jumps_and_long_gaps():
    stats = MovementStats()
    stats.update("upper", [0, 0], 0)
    stats.update("upper", [10, 0], 0.1)
    stats.update("upper", [11, 0], 2)
    assert stats.snapshot()["upper"]["distance_m"] == 0


def test_latest_mailbox_has_no_backlog():
    source = LatestFrameSource("unused", threading.Event())
    source.latest = FramePacket(None, 100, 1.0, 1, 25)
    assert source.read(1, timeout=0).sequence == 100
    assert source.read(100, timeout=0) is None


def test_restart_preserves_and_marks_interrupted(client):
    live_store.create_session("one", {"name": "saved", "calibration_version": "v1"})
    live_store.recover_sessions()
    result = client.get("/api/live/sessions/one").json()
    assert result["status"] == "interrupted" and result["calibration_version"] == "v1"
    assert client.post("/api/live/sessions/one/stop").json()["status"] == "interrupted"


def test_closed_artifacts_only_and_missing_session(client):
    live_store.create_session("one", {})
    folder = live_store.LIVE_RESULTS / "one"
    folder.mkdir()
    (folder / "camera_0000.mp4").write_bytes(b"closed")
    (folder / "camera_0001.mp4").write_bytes(b"open")
    (folder / "camera_index.json").write_text(json.dumps([{"file": "camera_0000.mp4", "closed": True}]), encoding="utf-8")
    listing = client.get("/api/live/sessions/one/artifacts").json()
    assert "camera_0000.mp4" in {item["name"] for item in listing}
    assert "camera_0001.mp4" not in {item["name"] for item in listing}
    assert client.get("/api/live/sessions/one/artifacts/camera_0001.mp4").status_code == 404
    assert client.get("/api/live/sessions/missing").status_code == 404


def test_camera_configuration_locked_during_session(client):
    live_api.manager.session_id = "active"
    assert client.put("/api/live/court", json={}).status_code == 409


def test_segments_preserve_short_gaps_and_separate_reconnects(tmp_path):
    import cv2
    writer = SegmentWriter(tmp_path, "test", fps=10)
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    writer.write(frame, 0, 1)
    writer.write(frame, 0.5, 1)
    writer.write(frame, 4, 2)
    writer.close_segment()
    index = json.loads((tmp_path / "test_index.json").read_text(encoding="utf-8"))
    assert len(index) == 2 and index[0]["frames"] == 6 and index[1]["frames"] == 1
    for item in index:
        capture = cv2.VideoCapture(str(tmp_path / item["file"]))
        assert capture.isOpened() and capture.read()[0]
        capture.release()


def fake_live_worker(config, output_dir, stop, events):
    events.put({"status": "running", "message": "test", "processed_frames": 1})
    stop.wait(20)
    (Path(output_dir) / "session_summary.json").write_text(json.dumps({"status": "stopped", "processed_frames": 7}), encoding="utf-8")


def test_process_stop_and_gpu_exclusion(client, monkeypatch):
    from web.api import compute_slot
    monkeypatch.setattr(live_api, "live_worker", fake_live_worker)
    config = live_api.CourtConfig().model_dump(exclude={"password"})
    config["calibration"] = {"version": "v1"}
    result = live_api.manager.start(config)
    assert compute_slot.lock.locked()
    assert client.put("/api/live/court", json={}).status_code == 409
    client.post(f"/api/live/sessions/{result['id']}/stop")
    live_api.manager.monitor.join(15)
    assert not live_api.manager.monitor.is_alive()
    assert live_store.get_session(result["id"])["status"] == "stopped"
    assert live_store.get_session(result["id"])["processed_frames"] == 7
    assert not compute_slot.lock.locked()


def test_worker_crash_is_interrupted(client, monkeypatch):
    from web.api import compute_slot
    monkeypatch.setattr(live_api, "live_worker", fake_live_worker)
    config = live_api.CourtConfig().model_dump(exclude={"password"})
    config["calibration"] = {"version": "v1"}
    result = live_api.manager.start(config)
    live_api.manager.process.terminate()
    live_api.manager.monitor.join(10)
    assert live_store.get_session(result["id"])["status"] == "interrupted"
    assert not compute_slot.lock.locked()


def test_private_files_and_spa_and_auth(client, monkeypatch):
    from web.api.app import app
    # No lifespan needed: isolated live database was already initialized by fixture.
    frontend = TestClient(app)
    monkeypatch.setenv("YUJIAN_PASSWORD", "operator-secret")
    assert frontend.get("/api/live/court").status_code == 401
    assert frontend.get("/api/live/court", auth=("operator", "wrong")).status_code == 401
    assert frontend.get("/api/live/court", auth=("operator", "operator-secret")).status_code == 200
    monkeypatch.delenv("YUJIAN_PASSWORD")
    assert frontend.get("/.runtime/live.sqlite3").status_code == 404
    from web.api.config import FRONTEND_DIST_DIR
    if FRONTEND_DIST_DIR.exists():
        assert frontend.get("/live").status_code == 200
    assert frontend.get("/api/not-a-route").status_code == 404
    response = frontend.put("/api/live/court", json={"rtsp_url": "rtsp://user:never-echo-this@host/video"})
    assert response.status_code == 422 and "never-echo-this" not in response.text
