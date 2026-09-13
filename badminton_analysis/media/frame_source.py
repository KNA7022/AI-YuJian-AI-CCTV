"""Bounded live acquisition. No network I/O takes place in the API event loop."""
import os
import threading
import time
from dataclasses import dataclass


@dataclass
class FramePacket:
    frame: object
    sequence: int
    captured_at: float
    generation: int
    fps: float


class LatestFrameSource:
    """One-slot mailbox; stale frames are replaced, never queued indefinitely.

    OpenCV's FFmpeg open/read timeouts bound normal shutdown. The owning analysis
    process is supervised separately so even a wedged native decoder can be killed.
    captured_at is host monotonic receipt time, not a claimed camera exposure time.
    """

    def __init__(self, url, stop_event, on_frame=None, timeout_ms=5000):
        self.url = url
        self.stop = stop_event
        self.on_frame = on_frame
        self.timeout_ms = timeout_ms
        self.condition = threading.Condition()
        self.latest = None
        self.status = "connecting"
        self.generation = 0
        self.thread = None
        self.error = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def _run(self):
        import cv2

        # Credentials may occur in native FFmpeg errors: suppress native logging.
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        cv2.setLogLevel(0)
        sequence = 0
        retry = 0
        while not self.stop.is_set():
            cap = None
            try:
                with self.condition:
                    self.status = "connecting" if self.generation == 0 else "reconnecting"
                    self.latest = None
                cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG, [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout_ms,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout_ms,
                ])
                if not cap.isOpened():
                    raise OSError("Camera unavailable")
                fps = cap.get(cv2.CAP_PROP_FPS)
                fps = fps if 1 <= fps <= 120 else 25.0
                self.generation += 1
                while not self.stop.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        raise OSError("Camera disconnected")
                    sequence += 1
                    packet = FramePacket(frame, sequence, time.monotonic(), self.generation, fps)
                    if self.on_frame:
                        self.on_frame(packet)
                    with self.condition:
                        self.latest = packet
                        self.status = "online"
                        self.condition.notify_all()
                    retry = 0
            except Exception:
                # Never return native exceptions containing the private RTSP URL.
                with self.condition:
                    self.latest = None
                    self.status = "reconnecting"
                    self.condition.notify_all()
            finally:
                if cap is not None:
                    cap.release()
            if not self.stop.is_set():
                self.stop.wait((1, 2, 5, 10)[min(retry, 3)])
                retry += 1
        self.status = "stopped"

    def read(self, after_sequence=0, timeout=1.0):
        with self.condition:
            self.condition.wait_for(
                lambda: self.stop.is_set() or (self.latest is not None and self.latest.sequence > after_sequence),
                timeout=timeout,
            )
            packet = self.latest
            return packet if packet is not None and packet.sequence > after_sequence else None

    def close(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread:
            self.thread.join(self.timeout_ms / 1000 + 2)


def snapshot_worker(url, destination, result):
    """Spawn-safe entry point for bounded, credential-redacted connection tests."""
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 2)
    os.close(null)
    import cv2

    source = LatestFrameSource(url, threading.Event()).start()
    try:
        packet = source.read(timeout=12)
        if packet is None:
            result.put({"error": "摄像头连接超时，请检查地址、账号及网络。"})
            return
        height, width = packet.frame.shape[:2]
        ok, jpeg = cv2.imencode(".jpg", packet.frame)
        if not ok:
            raise RuntimeError("JPEG encode failed")
        from pathlib import Path
        Path(destination).write_bytes(jpeg.tobytes())
        result.put({"width": width, "height": height, "fps": packet.fps})
    except Exception:
        result.put({"error": "无法读取摄像头画面，请检查码流格式和运行依赖。"})
    finally:
        source.close()
