"""Profile the live worker's per-frame stages to locate the real bottleneck.

Replicates the exact operations of badminton_analysis/live.py on real camera
frames and times each stage. No modules are modified.

Usage: python scripts/profile_live_stages.py [--seconds 12] [--device cuda:0]
"""
import argparse
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

CORNERS = [[430, 330], [2130, 330], [2410, 1300], [150, 1300]]
WIDTH, HEIGHT = 2560, 1440


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="rtsp://admin:admin@192.168.0.15/live/chn=0")
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--analysis-fps", type=int, default=25)
    parser.add_argument("--record", default="on", choices=["on", "off"],
                        help="whether to encode review segments (annotated/raw)")
    parser.add_argument("--warmup", type=int, default=5, help="frames to discard before timing")
    args = parser.parse_args()
    record = args.record == "on"

    from badminton_analysis.court.mapper import CourtMapper
    from badminton_analysis.detection.yolo_pose import YOLOPoseProcessor
    from badminton_analysis.visualization.player_pose import PlayerPoseVisualizer
    from badminton_analysis.visualization.stats import StatsVisualizer
    from badminton_analysis.live_features import LiveAnalytics
    from badminton_analysis.live_stats import MovementStats

    device = 0 if args.device == "cuda:0" else args.device
    pose = YOLOPoseProcessor("weights/yolo11n-pose.pt", device=device)
    print(f"pose device: {pose.device}")

    mapper = CourtMapper(CORNERS)
    visualizer = PlayerPoseVisualizer(pose, foot_offset_pixels=0, min_foot_confidence=0.3)
    visualizer.court_mapper = mapper
    overlay_stats = StatsVisualizer(WIDTH, HEIGHT, "zh")
    analytics = LiveAnalytics(False)
    trails = {side: deque(maxlen=60) for side in ("upper", "lower")}

    os_env = __import__("os").environ
    os_env.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    cap = cv2.VideoCapture(args.url, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
    if not cap.isOpened():
        print("cannot open camera")
        return 1

    from badminton_analysis.live import SegmentWriter
    out = Path(".runtime/profout")
    out.mkdir(parents=True, exist_ok=True)
    raw = SegmentWriter(out, "camera", fps=25)
    annotated = SegmentWriter(out, "annotated", fps=args.analysis_fps, seconds=10)

    stages = ["grab", "pose", "map_track", "analytics", "draw", "write_raw", "write_ann", "jpeg"]
    totals = {name: 0.0 for name in stages}
    counts = {name: 0 for name in stages}
    processed = 0
    started = time.monotonic()
    last_time = started

    while time.monotonic() - started < args.seconds:
        t = time.monotonic()
        ok, frame = cap.read()
        now = time.monotonic()
        if processed < args.warmup:
            processed += 1
            continue
        totals["grab"] += now - t; counts["grab"] += 1
        if not ok:
            continue
        captured = now

        t = time.monotonic()
        if record:
            raw.write(frame, captured - started, 1)
        totals["write_raw"] += time.monotonic() - t; counts["write_raw"] += 1

        work = frame.copy()

        t = time.monotonic()
        centroids, _, _ = visualizer.detect_players(work, 0, 0)
        totals["pose"] += time.monotonic() - t; counts["pose"] += 1

        t = time.monotonic()
        players = {"upper": [], "lower": []}
        for point in centroids:
            court = mapper.image_to_court(point)
            side = "upper" if court[1] < 6.7 else "lower"
            players[side].append((point, court.tolist()))
        records = {}
        for side, candidates in players.items():
            selected = candidates[0] if len(candidates) == 1 else None
            position = selected[1] if selected else None
            records[side] = {"image": list(selected[0]) if selected else None, "court": position,
                             "ambiguous": len(candidates) > 1, "speed": 0.0}
            if position is not None:
                trails[side].append(tuple(map(int, selected[0])))
        totals["map_track"] += time.monotonic() - t; counts["map_track"] += 1

        t = time.monotonic()
        analytics.update(records, captured - started, None, False)
        totals["analytics"] += time.monotonic() - t; counts["analytics"] += 1

        t = time.monotonic()
        pose_data = visualizer.current_pose_data
        if pose_data:
            visualizer._draw_skeleton_on_frame(work, pose_data["keypoints"], 0, 0)
        cv2.polylines(work, [np.array(CORNERS, dtype=np.int32)], True, (70, 210, 130), 2)
        for side, trail in trails.items():
            if len(trail) > 1:
                cv2.polylines(work, [np.array(trail, dtype=np.int32)], False, (255, 220, 50), 2)
        overlay_stats.draw_player_stats(work, analytics.stats(), 0)
        totals["draw"] += time.monotonic() - t; counts["draw"] += 1

        t = time.monotonic()
        if record:
            annotated.write(work, captured - started, 1)
        totals["write_ann"] += time.monotonic() - t; counts["write_ann"] += 1

        t = time.monotonic()
        preview = cv2.resize(work, (min(WIDTH, 1280), round(HEIGHT * min(WIDTH, 1280) / WIDTH)))
        cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 80])
        totals["jpeg"] += time.monotonic() - t; counts["jpeg"] += 1

        processed += 1
        now = time.monotonic()
        last_time = now

    cap.release()
    if record:
        raw.close_segment()
        annotated.close_segment()
    elapsed = time.monotonic() - started
    print(f"\nrecord={args.record}  processed {processed} frames in {elapsed:.1f}s = {processed/elapsed:.2f} FPS")
    print(f"{'stage':<12} {'total_ms':>10} {'per_frame_ms':>13} {'share':>7}")
    for name in stages:
        total_ms = totals[name] * 1000
        per = total_ms / max(1, counts[name])
        print(f"{name:<12} {total_ms:>10.1f} {per:>13.2f} {total_ms/(elapsed*1000)*100:>6.1f}%")
    print(f"\nnote: 'grab' includes waiting for the next camera frame (25fps = 40ms each)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
