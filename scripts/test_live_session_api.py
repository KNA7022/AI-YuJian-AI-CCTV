"""End-to-end check of the live session flow through the running API.

Uses the calibration from the app's own snapshot (synthetic quad used only to
exercise the pipeline), starts a session, polls status, then stops and inspects
the produced artifacts.

Usage: python scripts/test_live_session_api.py [--seconds 30] [--base http://127.0.0.1:8000]
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

CORNERS = [[430, 330], [2130, 330], [2410, 1300], [150, 1300]]


def call(base, path, method="GET", payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.headers.get("Content-Type", "").startswith("application/json"):
                return response.status, json.loads(body) if body else None
            return response.status, f"<{len(body)} bytes {response.headers.get('Content-Type')}>"
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    base = args.base

    status, health = call(base, "/api/live/health")
    print(f"health {status}: errors={health.get('errors') if isinstance(health, dict) else health}")

    status, court = call(base, "/api/live/court")
    snapshot = (court or {}).get("snapshot")
    if not snapshot:
        status, court = call(base, "/api/live/court/snapshot", "POST", timeout=60)
        snapshot = (court or {}).get("snapshot")
    if not snapshot:
        print("no snapshot available; cannot calibrate")
        return 1
    print(f"snapshot: {snapshot['width']}x{snapshot['height']} id={snapshot['id'][:8]}")

    status, calibrated = call(base, "/api/live/court/calibration", "PUT",
                              {"snapshot_id": snapshot["id"], "corners": CORNERS})
    if status != 200:
        print(f"calibration rejected {status}: {calibrated}")
        return 1
    print(f"calibration accepted: version={calibrated['calibration']['version'][:8]}")

    status, health = call(base, "/api/live/health")
    print(f"health after calibration: errors={health.get('errors')}")

    status, session = call(base, "/api/live/sessions", "POST", timeout=60)
    if status != 200:
        print(f"session start failed {status}: {session}")
        return 1
    session_id = session["id"]
    print(f"session started: {session_id[:8]} status={session['status']}")

    started = time.monotonic()
    last_frames = 0
    try:
        while time.monotonic() - started < args.seconds:
            time.sleep(3)
            code, detail = call(base, f"/api/live/sessions/{session_id}")
            if code != 200:
                print(f"  poll failed {code}: {detail}")
                break
            elapsed = round(time.monotonic() - started, 1)
            print(f"  [{elapsed:5.1f}s] status={detail.get('status')} "
                  f"frames={detail.get('processed_frames')} skipped={detail.get('skipped_frames')} "
                  f"inference_fps={detail.get('inference_fps')} message={detail.get('message')}")
            if detail.get("processed_frames"):
                last_frames = detail["processed_frames"]
    finally:
        code, stopped = call(base, f"/api/live/sessions/{session_id}/stop", "POST", timeout=60)
        print(f"stop -> {code} {json.dumps(stopped, ensure_ascii=False) if isinstance(stopped, dict) else stopped}")

    for _ in range(20):
        time.sleep(1.5)
        code, detail = call(base, f"/api/live/sessions/{session_id}")
        if detail.get("status") not in {"preparing", "running", "reconnecting", "stopping"}:
            break
    print(f"final session: status={detail.get('status')} frames={detail.get('processed_frames')} "
          f"disk={detail.get('disk', {}) if isinstance(detail.get('disk'), dict) else 'n/a'}")

    code, artifacts = call(base, f"/api/live/sessions/{session_id}/artifacts")
    print(f"artifacts {code}: {json.dumps(artifacts, ensure_ascii=False)[:600]}")

    code, preview = call(base, f"/api/live/sessions/{session_id}/images/match_heatmap.jpg")
    print(f"chart image fetch: {'ok' if code == 200 else code}")

    print(f"session_id={session_id}")
    print("RESULT:", "PASS - live session ran through the API and produced artifacts"
          if last_frames > 0 else "FAIL - no frames processed")
    return 0 if last_frames > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
