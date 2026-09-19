"""Controlled run of the live analysis worker against the real camera.

Verifies that the spawn-based live pipeline loads the pose model, connects to the
RTSP camera, processes frames at the configured rate, and writes review artifacts.

Usage:
    python scripts/test_live_worker.py --seconds 45 [--url rtsp://...] [--out .runtime/livecheck]
"""
import argparse
import json
import multiprocessing
import queue
import shutil
import sys
import time
from pathlib import Path

# Synthetic court quad meeting the API's ordering constraints (TL, TR, BR, BL);
# it is *not* a real calibration and exists only to exercise the pipeline.
CORNERS = [[430, 330], [2130, 330], [2410, 1300], [150, 1300]]
WIDTH, HEIGHT = 2560, 1440


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="rtsp://admin:admin@192.168.0.15/live/chn=0")
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--out", default=".runtime/livecheck")
    args = parser.parse_args()

    output = Path(args.out)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    from badminton_analysis.live import live_worker

    config = {
        "language": "zh",
        "pose_family": "yolo-pose",
        "pose_model": str(Path("weights/yolo11n-pose.pt").resolve()),
        "ball_model": str(Path("weights/yolo11s-ball.pt").resolve()),
        "ball_enabled": False,
        "device": "cpu",
        "analysis_fps": 10,
        "record_video": True,
        "record_fps": 25,
        "max_duration_minutes": 1,
        "min_free_gb": 0.5,
        "keep_audio": False,
        "visualize_positions": True,
        "auto_rallies": False,
        "show_skeletons": True,
        "show_player_trajectories": True,
        "show_court_trajectory": True,
        "show_shuttlecock_trajectory": False,
        "show_player_stats": True,
        "rtsp_url": args.url,
        "calibration": {"version": "test", "corners": CORNERS, "width": WIDTH, "height": HEIGHT},
    }

    context = multiprocessing.get_context("spawn")
    stop = context.Event()
    events = context.Queue(maxsize=8)
    process = context.Process(target=live_worker, args=(config, str(output), stop, events), daemon=True)

    started = time.monotonic()
    process.start()
    print(f"live_worker pid={process.pid} started; running for {args.seconds:.0f}s")

    seen_statuses = []
    last_stats = None
    try:
        while time.monotonic() - started < args.seconds and process.is_alive():
            try:
                event = events.get(timeout=1.0)
            except queue.Empty:
                continue
            status = event.get("status")
            if status and (not seen_statuses or seen_statuses[-1] != status):
                seen_statuses.append(status)
                print(f"[{time.monotonic()-started:6.1f}s] status={status} msg={event.get('message')}")
            if status == "running":
                last_stats = {key: event.get(key) for key in
                              ("processed_frames", "skipped_frames", "source_fps", "inference_fps", "elapsed_sec")}
    finally:
        print("signalling stop...")
        stop.set()
        process.join(25)
        if process.is_alive():
            print("worker ignored stop -> terminating")
            process.terminate()
            process.join(5)
        events.close()

    print(f"worker exitcode={process.exitcode}")
    print(f"status transitions: {seen_statuses}")
    if last_stats:
        print(f"last running event: {json.dumps(last_stats, ensure_ascii=False)}")

    print("--- artifacts ---")
    produced = sorted(output.iterdir())
    for item in produced:
        print(f"  {item.name}  {item.stat().st_size} bytes")

    summary_path = output / "session_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        print("session_summary:", json.dumps({k: summary.get(k) for k in
              ("status", "message", "processed_frames", "skipped_frames", "elapsed_sec")}, ensure_ascii=False))

    detections = output / "detections.jsonl"
    if detections.exists():
        lines = detections.read_text(encoding="utf-8").strip().splitlines()
        print(f"detections.jsonl lines: {len(lines)}")
        if lines:
            print("first record:", lines[0][:300])

    ok = bool(last_stats and last_stats.get("processed_frames", 0) > 0)
    print("RESULT:", "PASS - live analysis pipeline processed camera frames" if ok
          else "FAIL - no frames were processed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
