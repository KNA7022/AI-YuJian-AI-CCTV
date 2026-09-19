"""Isolate YOLO pose cost: full frame vs pre-resized, and raw GPU inference.

Usage: python scripts/bench_pose_paths.py
"""
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

IMAGE = Path(".runtime/verify/app_snapshot.jpg")
MODEL = "weights/yolo11n-pose.pt"
FULL = cv2.imread(str(IMAGE))
print(f"input frame: {FULL.shape[1]}x{FULL.shape[0]}")

model = YOLO(MODEL)


def timed(label, fn, iterations=15, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    started = time.monotonic()
    for _ in range(iterations):
        fn()
    torch.cuda.synchronize()
    elapsed = time.monotonic() - started
    print(f"{label:<44} {elapsed/iterations*1000:8.1f} ms/frame  {iterations/elapsed:7.2f} FPS")


# 1. current code path: full 2560x1440 frame -> model(imgsz default 640)
timed("full frame -> model(device=0)", lambda: model(FULL, conf=0.25, device=0, verbose=False))

# 2. same, but explicitly the default imgsz
timed("full frame -> model(imgsz=640, device=0)",
      lambda: model(FULL, conf=0.25, device=0, imgsz=640, verbose=False))

# 3. pre-resized to 640 wide (shrinks CPU letterbox work)
small = cv2.resize(FULL, (640, 360))
timed("pre-resized 640x360 -> model(device=0)",
      lambda: model(small, conf=0.25, device=0, verbose=False))

# 4. rectify + GPU-side resize: half size
half = cv2.resize(FULL, (1280, 720))
timed("pre-resized 1280x720 -> model(device=0)",
      lambda: model(half, conf=0.25, device=0, verbose=False))

# 5. raw network inference only, tensor already on GPU at 640x640
tensor = torch.from_numpy(cv2.cvtColor(cv2.resize(FULL, (640, 640)), cv2.COLOR_BGR2RGB))
tensor = tensor.permute(2, 0, 1).float().div(255).unsqueeze(0).cuda()
net = model.model
with torch.no_grad():
    for _ in range(3):
        net(tensor)
    torch.cuda.synchronize()
    started = time.monotonic()
    for _ in range(15):
        net(tensor)
    torch.cuda.synchronize()
    elapsed = time.monotonic() - started
print(f"{'GPU-only net(640x640 tensor)':<44} {elapsed/15*1000:8.1f} ms/frame  {15/elapsed:7.2f} FPS")

# 6. CPU-side letterbox + BGR->RGB + normalize cost alone
def preprocess_only():
    image = cv2.resize(FULL, (640, 640))
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    arr = np.ascontiguousarray(rgb.transpose(2, 0, 1), dtype=np.float32) / 255.0
    torch.from_numpy(arr)

timed("CPU preprocessing only (resize+RGB+norm)", preprocess_only, iterations=30)
