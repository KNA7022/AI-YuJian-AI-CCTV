"""One-shot RTSP connectivity probe for local deployment verification.

Reads a bounded number of frames from the configured camera URL and writes
sample frames to a directory for visual inspection.

Usage:
    python scripts/verify_rtsp.py [--url rtsp://...] [--out .runtime/verify] [--frames 5]

Never prints the camera URL with credentials; the URL is redacted in all output.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path


def redact(url: str) -> str:
    """Strip credentials from an RTSP/HTTP URL for safe logging."""
    return re.sub(r"//[^/@]*@", "//<credentials>@", url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe an RTSP camera and save sample frames.")
    parser.add_argument("--url", required=True, help="Camera URL (rtsp://...)")
    parser.add_argument("--out", default=".runtime/verify", help="Directory for sample frames")
    parser.add_argument("--frames", type=int, default=5, help="Frames to read and save")
    parser.add_argument("--timeout-ms", type=int, default=8000, help="Open/read timeout in ms")
    args = parser.parse_args()

    safe_url = redact(args.url)
    print(f"camera_url_redacted: {safe_url}")
    print(f"opencv_ffmpeg_probe: {safe_url}")

    try:
        import cv2
    except ImportError as exc:
        print(f"FAIL import cv2: {exc}")
        return 2

    print(f"opencv_version: {cv2.__version__}")

    import os
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    # cv2.setLogLevel was removed in OpenCV 5.x; fall back to the legacy utility.
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)
    elif hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    cap = cv2.VideoCapture(args.url, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, args.timeout_ms,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, args.timeout_ms,
    ])
    open_sec = round(time.monotonic() - started, 2)
    print(f"isOpened: {cap.isOpened()} (open took {open_sec}s)")
    if not cap.isOpened():
        print("RESULT: FAIL - could not open RTSP stream")
        cap.release()
        return 3

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    backend = cap.getBackendName()
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_text = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
    print(f"backend: {backend}")
    print(f"reported_width_height: {width}x{height}")
    print(f"reported_fps: {fps}")
    print(f"reported_fourcc: {fourcc_text!r}")

    saved = 0
    read_failures = 0
    first_frame_sec = None
    for index in range(args.frames):
        tick = time.monotonic()
        ok, frame = cap.read()
        if not ok or frame is None:
            read_failures += 1
            print(f"frame {index}: read failed")
            break
        if first_frame_sec is None:
            first_frame_sec = round(time.monotonic() - started, 2)
        h, w = frame.shape[:2]
        if index == 0 or index == args.frames - 1:
            target = out_dir / f"frame_{index:03d}.jpg"
            cv2.imwrite(str(target), frame)
            print(f"frame {index}: {w}x{h} saved -> {target} (read {round(time.monotonic()-tick, 3)}s)")
        else:
            print(f"frame {index}: {w}x{h} (read {round(time.monotonic()-tick, 3)}s)")
        saved += 1

    cap.release()
    elapsed = round(time.monotonic() - started, 2)

    summary = {
        "url_redacted": safe_url,
        "opencv_version": cv2.__version__,
        "backend": backend,
        "is_opened": True,
        "reported_width": width,
        "reported_height": height,
        "reported_fps": fps,
        "fourcc": fourcc_text,
        "frames_requested": args.frames,
        "frames_saved": saved,
        "read_failures": read_failures,
        "first_frame_after_sec": first_frame_sec,
        "total_elapsed_sec": elapsed,
        "sample_dir": str(out_dir),
    }
    (out_dir / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESULT:", json.dumps(summary, ensure_ascii=False))
    if saved == 0:
        print("RESULT: FAIL - stream opened but no frames could be decoded")
        return 4
    print("RESULT: PASS - network camera reachable and decoding frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
