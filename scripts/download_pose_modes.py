"""Fetch extra RTMPose/RTMO tiers from the official OpenMMLab model URLs."""
import hashlib
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

POSE = "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
RTMO = "https://download.openmmlab.com/mmpose/v1/projects/rtmo/onnx_sdk/"
ASSETS = [
    (POSE, "rtmpose-t_simcc-body7_pt-body7_420e-256x192-026a1439_20230504"),
    (POSE, "rtmpose-m_simcc-body7_pt-body7_420e-256x192-e48f03d0_20230504"),
    (RTMO, "rtmo-m_16xb16-600e_body7-640x640-39e78cc4_20231211"),
    (RTMO, "rtmo-l_16xb16-600e_body7-640x640-b37118ce_20231211"),
]


def fetch(asset):
    directory = Path(__file__).resolve().parents[1]/"weights"
    directory.mkdir(exist_ok=True)
    base, stem = asset
    target = directory/(stem+".onnx")
    url = base+stem+".zip"
    if not target.exists():
        with urlopen(url, timeout=120) as response:
            data = response.read()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [name for name in archive.namelist() if name.endswith(".onnx")]
            if len(members) != 1:
                raise RuntimeError(f"Unexpected model archive: {stem}")
            # Never extract arbitrary archive paths.
            target.write_bytes(archive.read(members[0]))
    return {"file": target.name, "source": url, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=2) as executor:
        for item in executor.map(fetch, ASSETS):
            print(json.dumps(item))
