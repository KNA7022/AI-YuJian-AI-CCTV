"""Benchmark YOLO pose inference on CPU vs GPU using a real camera frame.

Usage: python scripts/bench_pose_gpu.py [image]
"""
import sys
import time
from pathlib import Path

import cv2

IMAGE = Path(sys.argv[1] if len(sys.argv) > 1 else ".runtime/verify/app_snapshot.jpg")
MODEL = "weights/yolo11n-pose.pt"


def bench(device, iterations=12, warmup=3):
    from ultralytics import YOLO
    import torch

    if device != "cpu" and not torch.cuda.is_available():
        return None
    model = YOLO(MODEL)
    frame = cv2.imread(str(IMAGE))
    if frame is None:
        raise SystemExit(f"cannot read {IMAGE}")

    for _ in range(warmup):
        model(frame, conf=0.25, device=device, verbose=False)
    if device != "cpu":
        torch.cuda.synchronize()

    started = time.monotonic()
    for _ in range(iterations):
        result = model(frame, conf=0.25, device=device, verbose=False)[0]
    if device != "cpu":
        torch.cuda.synchronize()
    elapsed = time.monotonic() - started

    people = 0 if result.keypoints is None or result.keypoints.xy is None else int(result.keypoints.xy.shape[0])
    per_frame_ms = elapsed / iterations * 1000
    return {"device": device, "fps": round(iterations / elapsed, 2),
            "ms_per_frame": round(per_frame_ms, 1), "people_detected": people,
            "frame": f"{frame.shape[1]}x{frame.shape[0]}"}


def main() -> int:
    import torch
    print(f"torch {torch.__version__} | cuda_available {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"gpu: {torch.cuda.get_device_name(0)}")
    for device in ("cpu", 0):
        try:
            result = bench(device)
        except Exception as exc:
            print(f"device {device}: FAILED - {exc}")
            continue
        if result is None:
            print(f"device {device}: unavailable")
            continue
        print(f"device {result['device']}: {result['fps']} FPS, {result['ms_per_frame']} ms/frame, "
              f"people={result['people_detected']}, frame={result['frame']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
