"""Reproduce the live API's snapshot worker path exactly, with diagnostics visible.

Usage: python scripts/test_snapshot_worker.py "<rtsp url with credentials>"
"""
import multiprocessing
import queue
import sys
import time
from pathlib import Path


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "rtsp://admin:admin@192.168.0.15/live/chn=0"
    dest = Path(".runtime/verify/worker_snapshot.jpg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    from badminton_analysis.media.frame_source import snapshot_worker

    context = multiprocessing.get_context("spawn")
    result = context.Queue(maxsize=1)
    process = context.Process(target=snapshot_worker, args=(url, str(dest), result), daemon=True)

    started = time.monotonic()
    process.start()
    print(f"worker pid={process.pid} started")
    info = None
    try:
        info = result.get(timeout=18)
        print(f"got result after {time.monotonic()-started:.1f}s: {info}")
    except queue.Empty:
        print(f"QUEUE EMPTY after {time.monotonic()-started:.1f}s (worker timed out)")
    finally:
        process.join(2)
        if process.is_alive():
            print("worker still alive -> terminating")
            process.terminate()
            process.join(3)
        result.close()

    print(f"exitcode={process.exitcode}")
    print(f"file exists: {dest.exists()} size: {dest.stat().st_size if dest.exists() else 0}")
    if dest.exists():
        import cv2
        image = cv2.imread(str(dest))
        print(f"decoded shape: {None if image is None else image.shape}")
    return 0 if dest.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
