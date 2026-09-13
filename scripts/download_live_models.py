"""Download the original release assets and verify their published SHA-256."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

BASE = "https://github.com/yo-WASSUP/Good-Badminton/releases/download/v0.1.0/"
ASSETS = {
    "yolo11n-pose.pt": "869e83fcdffdc7371fa4e34cd8e51c838cc729571d1635e5141e3075e9319dc0",
    "yolo11s-ball.pt": "c21113960fadce7f96b9f70f86802142482775405f60a9761328491868edf31b",
    "rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx": "d0703d40d19f3921da51ae725402d5fdae4d2478c7442072d3101bd396f370d8",
    "rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx": "9aeb635b83f86aea45cf45d85798f7eba1a162de8e0d721c44e54fe5eebaf47d",
    "yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx": "1450966de24902b18aada1a78913d7efd8fc8dcd51bd4d0d5591476bd4a38821",
}


def main():
    directory = Path(__file__).resolve().parents[1] / "weights"
    directory.mkdir(exist_ok=True)
    for name, expected in ASSETS.items():
        destination = directory / name
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Existing {name} differs from the release; preserve or rename your custom model before downloading.")
            print(f"Verified: {name}")
            continue
        temporary = destination.with_suffix(".download")
        digest = hashlib.sha256()
        try:
            with urlopen(BASE + name, timeout=90) as source, temporary.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise RuntimeError(f"Checksum mismatch for {name}")
            temporary.replace(destination)
            print(f"Downloaded and verified: {name}")
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
