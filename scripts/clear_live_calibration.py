"""Remove the synthetic calibration and snapshot from the live court config.

The API deliberately preserves calibration when the camera source is unchanged, so
a test-driven calibration must be cleared directly. Camera address and credentials
are left untouched.

Usage: python scripts/clear_live_calibration.py [--dir .runtime]
"""
import argparse
import json
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".runtime")
    args = parser.parse_args()

    database = Path(args.dir) / "live.sqlite3"
    if not database.exists():
        print(f"no database at {database}")
        return 1

    with sqlite3.connect(database) as db:
        row = db.execute("SELECT payload FROM court WHERE id=1").fetchone()
        if row is None:
            print("no stored court config")
            return 0
        payload = json.loads(row[0])
        removed = [key for key in ("calibration", "snapshot") if payload.get(key)]
        for key in removed:
            payload[key] = None
        db.execute("UPDATE court SET payload=? WHERE id=1", (json.dumps(payload, ensure_ascii=False),))
        print(f"cleared: {removed}")
        print(f"kept keys: rtsp_url={payload.get('rtsp_url')} username={payload.get('username')} "
              f"has_password={bool(payload.get('password'))} device={payload.get('device')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
