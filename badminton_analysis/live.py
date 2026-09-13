"""Live singles pipeline reusing the project's detectors and court mapper."""
import json
import os
import queue
import shutil
import threading
import time
from collections import deque
from pathlib import Path

from .live_stats import MovementStats
from .media.frame_source import LatestFrameSource
from .live_features import LiveAnalytics
from .media.files import replace_when_ready


def atomic_json(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    replace_when_ready(temporary, path)


class SegmentWriter:
    """Silent MP4 review segments with a host-time presentation timeline.

    Repeats the previous frame for short sampling gaps. A disconnect starts a new
    segment; no frames are invented across it. Raw and annotated paths have their
    own indices, so they need not have matching frame counts.
    """

    def __init__(self, directory, prefix, fps=10.0, seconds=60):
        self.directory = Path(directory)
        self.prefix = prefix
        self.fps = fps
        self.seconds = seconds
        self.writer = None
        self.segments = []
        self.previous = None
        self.count = 0
        self.started = 0
        self.last_time = None
        self.generation = None

    def write(self, frame, timestamp, generation):
        import cv2
        shape = (frame.shape[1], frame.shape[0])
        if self.writer is not None and (generation != self.generation or shape != self.shape or
                                       timestamp - self.started >= self.seconds or timestamp - self.last_time > 1.0):
            self.close_segment()
        if self.writer is None:
            self.shape = shape
            self.started = timestamp
            self.generation = generation
            self.count = 0
            name = f"{self.prefix}_{len(self.segments):04d}.mp4"
            self.writer = cv2.VideoWriter(str(self.directory / name), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, shape)
            if not self.writer.isOpened():
                self.writer.release()
                self.writer = None
                raise RuntimeError("无法创建录像，请检查编码器和存储路径。")
            self.segments.append({"file": name, "start_sec": timestamp, "fps": self.fps, "closed": False})
        target = int((timestamp - self.started) * self.fps)
        while self.count < target:
            self.writer.write(self.previous if self.previous is not None else frame)
            self.count += 1
        if self.count == target:
            self.writer.write(frame)
            self.count += 1
        self.previous = frame.copy()
        self.last_time = timestamp

    def close_segment(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            self.segments[-1].update(end_sec=self.last_time, frames=self.count, closed=True)
            atomic_json(self.directory / f"{self.prefix}_index.json", self.segments)
        self.previous = None


def live_worker(config, output_dir, stop, events):
    """Spawn entry point. Only structured, credential-free events leave this process."""
    # Native decoder messages can contain RTSP authentication. Never persist them.
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 2)
    os.close(null)
    output = Path(output_dir)
    config = {"language": "zh", "pose_family": "yolo-pose", "pose_mode": "balanced",
              "visualize_positions": True, "auto_rallies": True, "show_skeletons": True,
              "show_player_trajectories": True, "show_court_trajectory": True,
              "show_shuttlecock_trajectory": True, "show_player_stats": True, **config}
    model_config = Path(__file__).resolve().parents[1] / ".runtime" / "ultralytics"
    model_config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(model_config))
    source = None
    raw = None
    annotated = None
    detections = None
    stats = MovementStats()
    analytics = LiveAnalytics(config["auto_rallies"] and config["ball_enabled"])
    last_charts = 0.0
    last_manual = 0
    trails = {side: deque(maxlen=60) for side in ("upper", "lower")}
    final_status = "stopped"
    message = "分析已停止。"
    processed = 0
    skipped = 0
    started = time.monotonic()
    last_packet_at = started
    last_event = 0.0
    heatmap = None
    recording_error = threading.Event()

    def emit(payload):
        try:
            events.put_nowait(payload)
        except queue.Full:
            pass

    try:
        import cv2
        import numpy as np
        from .court.mapper import CourtMapper
        from .detection.yolo_pose import YOLOPoseProcessor
        from .detection.shuttlecock import ShuttlecockTracker
        from .visualization.player_pose import PlayerPoseVisualizer
        from .visualization.stats import StatsVisualizer
        from .visualization.court_trajectory import CourtTrajectoryVisualizer

        calibration = config["calibration"]
        mapper = CourtMapper(calibration["corners"])
        if config["pose_family"] == "yolo-pose":
            pose = YOLOPoseProcessor(config["pose_model"], device=config["device"])
        else:
            from .detection.rtmpose import RTMPoseProcessor
            pose = RTMPoseProcessor(mode=config["pose_mode"], pose_family=config["pose_family"],
                                    device="cuda" if config["device"] == "cuda:0" else config["device"])
            if pose.wholebody is None:
                raise RuntimeError("无法加载所选姿态模型，请检查本地 ONNX 权重及运行环境。")
        overlay_stats = StatsVisualizer(calibration["width"], calibration["height"], config["language"])
        court_visualizer = CourtTrajectoryVisualizer()
        player_visualizer = PlayerPoseVisualizer(pose, foot_offset_pixels=0, min_foot_confidence=0.3)
        player_visualizer.court_mapper = mapper
        ball_model = None
        if config["ball_enabled"]:
            from ultralytics import YOLO
            ball_model = YOLO(config["ball_model"])
        ball = ShuttlecockTracker(ball_model)
        ball.show_trajectory = config["show_shuttlecock_trajectory"]
        if config["device"] == "cpu":
            ball.ultra_device = "cpu"
        heatmap = {side: np.zeros((67, 31), dtype=np.int64) for side in ("upper", "lower")}
        atomic_json(output / "metadata.json", {
            "schema_version": "live-1.0", "camera_id": "court-1", "calibration": calibration,
            "pose_model": Path(config["pose_model"]).name,
            "ball_model": Path(config["ball_model"]).name if config["ball_enabled"] else None,
            "mode": "singles", "clock": "host_monotonic_receipt", "audio": config.get("keep_audio", True),
            "started_at_unix": time.time()-(time.monotonic()-started),
            "rally_mode": "automatic_estimate" if config["auto_rallies"] else "manual",
            "language": config["language"], "pose_family": config["pose_family"], "pose_mode": config["pose_mode"],
            "recording": "host-time resampled review segments; source audio/video in source.m3u8 when enabled",
        })
        raw = SegmentWriter(output, "camera", fps=config["record_fps"])
        annotated = SegmentWriter(output, "annotated", fps=config["analysis_fps"], seconds=10)
        detections = (output / "detections.jsonl").open("w", encoding="utf-8")

        def record(packet):
            if config["record_video"]:
                try:
                    raw.write(packet.frame, packet.captured_at - started, packet.generation)
                except Exception:
                    recording_error.set()

        source = LatestFrameSource(config["rtsp_url"], stop, on_frame=record).start()
        sequence = 0
        generation = 0
        next_analysis = 0.0
        last_disk_check = 0.0
        active_since = time.monotonic()
        emit({"status": "preparing", "message": "模型已加载，正在连接摄像头。"})
        while not stop.is_set():
            now = time.monotonic()
            if now - started > config["max_duration_minutes"] * 60:
                message = "达到会话时长上限，已自动停止。"
                break
            if recording_error.is_set():
                raise RuntimeError("录像写入失败，请检查磁盘。")
            if now - last_disk_check > 5:
                last_disk_check = now
                if shutil.disk_usage(output).free < config["min_free_gb"] * 1024 ** 3:
                    raise RuntimeError("可用磁盘空间不足，分析已安全停止。")
            packet = source.read(sequence, timeout=0.5)
            if packet is None:
                if now - last_packet_at > 60:
                    raise RuntimeError("摄像头超过 60 秒未恢复，请检查网络后重新开始。")
                if now - last_event > 1:
                    emit({"status": "reconnecting", "message": "等待摄像头恢复连接。", "elapsed_sec": round(now-started, 1)})
                    last_event = now
                continue
            last_packet_at = packet.captured_at
            if packet.captured_at < next_analysis:
                stop.wait(min(0.05, next_analysis - packet.captured_at))
                continue
            skipped += max(0, packet.sequence - sequence - 1)
            sequence = packet.sequence
            next_analysis = packet.captured_at + 1 / config["analysis_fps"]
            if packet.generation != generation:
                stats.reset_continuity()
                analytics.disconnect(packet.captured_at-started)
                ball.clear_trajectory()
                for trail in trails.values():
                    trail.clear()
                generation = packet.generation
            frame = packet.frame.copy()
            height, width = frame.shape[:2]
            if width != calibration["width"] or height != calibration["height"]:
                raise RuntimeError("摄像头分辨率与标定不一致，请重新抓图并标定。")
            centroids, _, _ = player_visualizer.detect_players(frame, 0, 0)
            players = {"upper": [], "lower": []}
            for point in centroids:
                court = mapper.image_to_court(point)
                side = "upper" if court[1] < 6.7 else "lower"
                players[side].append((point, court.tolist()))
            timestamp = packet.captured_at - started
            records = {}
            ambiguous = False
            for side, candidates in players.items():
                # Multiple people in a half-court are ambiguous in singles mode.
                # Do not overwrite one person's record with another's position.
                selected = candidates[0] if len(candidates) == 1 else None
                ambiguous = ambiguous or len(candidates) > 1
                position = selected[1] if selected else None
                stats.update(side, position, timestamp)
                records[side] = {"image": list(selected[0]) if selected else None, "court": position,
                                 "ambiguous": len(candidates) > 1, "speed": stats.totals[side]["speed_mps"]}
                if position is not None:
                    trails[side].append(tuple(map(int, selected[0])))
                    x, y = position
                    if 0 <= x < 6.1 and 0 <= y < 13.4:
                        heatmap[side][min(66, int(y / 13.4 * 67)), min(30, int(x / 6.1 * 31))] += 1
                else:
                    trails[side].clear()
            # Run ball detection on the clean frame before drawing any overlays.
            ball_position = ball.detect_ball(frame)
            ball.update_trajectory(ball_position)
            manual_file = output / "rallies.json"
            manual = False
            if manual_file.exists():
                try:
                    count = len(json.loads(manual_file.read_text(encoding="utf-8")))
                    manual = count > last_manual
                    last_manual = count
                except (OSError, ValueError):
                    pass
            analytics.update(records, timestamp,
                             ball_position if ball.get_last_detection()["accepted"] else None, manual)
            record_data = {"schema_version": "live-1.0", "frame": sequence, "time_sec": timestamp,
                           "generation": generation, "players": records, "shuttlecock": ball.get_last_detection(),
                           "rally_id": analytics.rallies.count, "rally_active": analytics.rallies.active}
            detections.write(json.dumps(record_data, ensure_ascii=False) + "\n")
            processed += 1
            pose_data = player_visualizer.current_pose_data
            if pose_data and config["show_skeletons"]:
                player_visualizer._draw_skeleton_on_frame(frame, pose_data["keypoints"], 0, 0)
            cv2.polylines(frame, [np.array(calibration["corners"], dtype=np.int32)], True, (70, 210, 130), 2)
            for side, trail in trails.items():
                if len(trail) > 1 and config["show_player_trajectories"]:
                    color = (255, 220, 50) if side == "upper" else (80, 100, 255)
                    cv2.polylines(frame, [np.array(trail, dtype=np.int32)], False, color, 2)
            ball.handle_visualization(frame)
            if config["show_player_stats"]:
                overlay_stats.draw_player_stats(frame, analytics.stats(), analytics.rallies.count)
            if config["show_court_trajectory"]:
                frame = court_visualizer.draw_overlay(frame, analytics.positions)
            if config["record_video"]:
                annotated.write(frame, timestamp, generation)
            now = time.monotonic()
            if now-last_charts >= 2:
                if config["visualize_positions"]:
                    analytics.write_charts(output, config["language"])
                atomic_json(output / "live_summary.json", {"stats": analytics.stats(), "rally": analytics.rallies.snapshot(),
                                                           "time_sec": timestamp, "processed_frames": processed})
                last_charts = now
            if now - last_event >= 0.4:
                detections.flush()
                preview = cv2.resize(frame, (min(width, 1280), round(height * min(width, 1280) / width)))
                ok, jpg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 80])
                emit({"status": "running", "message": "同一半场存在多人，相关人物统计暂停。" if ambiguous else "单打分析运行中。",
                      "processed_frames": processed, "skipped_frames": skipped, "source_fps": packet.fps,
                      "inference_fps": round(processed / max(0.01, now-active_since), 2),
                      "frame_age_sec": round(now-packet.captured_at, 3), "elapsed_sec": round(now-started, 1),
                      "stats": analytics.stats(), "rally": analytics.rallies.snapshot(), "ball_enabled": config["ball_enabled"],
                      "chart_revision": int(last_charts), "visualize_positions": config["visualize_positions"],
                      "language": config["language"], "pose_family": config["pose_family"], "pose_mode": config["pose_mode"],
                      "preview": jpg.tobytes() if ok else None})
                last_event = now
    except Exception as exc:
        final_status = "failed"
        # Only our own known messages are user-facing; arbitrary library errors may
        # contain private URLs or local secrets.
        message = str(exc) if isinstance(exc, RuntimeError) and str(exc).startswith(("录像", "可用", "摄像头", "无法")) else "分析进程失败，请检查模型、依赖和设备配置。"
    finally:
        if source:
            source.close()
        if raw:
            raw.close_segment()
        if annotated:
            annotated.close_segment()
        if detections:
            detections.close()
        if heatmap is not None and config["visualize_positions"]:
            analytics.write_charts(output, config["language"])
            # Bounded accumulators; no in-memory history grows with session length.
            import cv2
            import numpy as np
            for side, grid in heatmap.items():
                scaled = (grid / max(1, grid.max()) * 255).astype(np.uint8)
                picture = cv2.applyColorMap(cv2.resize(scaled, (305, 670)), cv2.COLORMAP_TURBO)
                ok, jpg = cv2.imencode(".jpg", picture)
                if ok:
                    (output / f"heatmap_{side}.jpg").write_bytes(jpg.tobytes())
        analytics.rallies.finish(time.monotonic()-started)
        summary = {"status": final_status, "message": message, "stats": analytics.stats(),
                   "rally": analytics.rallies.snapshot(), "visualize_positions": config["visualize_positions"],
                   "processed_frames": processed, "skipped_frames": skipped,
                   "elapsed_sec": round(time.monotonic()-started, 1), "ball_enabled": config["ball_enabled"]}
        atomic_json(output / "session_summary.json", summary)
        # Final status is also persisted to disk, so a full IPC queue cannot lose it.
        emit(summary)
