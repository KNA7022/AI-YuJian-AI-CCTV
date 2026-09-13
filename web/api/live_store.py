"""Private live configuration and transactional session storage.

Kept outside /storage and /results, both of which the legacy app serves publicly.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT_DIR

PRIVATE_DIR = Path(os.environ.get("YUJIAN_PRIVATE_DIR", str(ROOT_DIR / ".runtime")))
LIVE_RESULTS = ROOT_DIR / "results" / "live"
ACTIVE = ("preparing", "running", "reconnecting", "stopping")


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(PRIVATE_DIR / "live.sqlite3", timeout=10) as db:
        db.row_factory = sqlite3.Row
        yield db


def init_live_db():
    LIVE_RESULTS.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS court (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_live_session ON sessions((1))
                WHERE status IN ('preparing','running','reconnecting','stopping');
        """)


def get_court():
    with connection() as db:
        row = db.execute("SELECT payload FROM court WHERE id=1").fetchone()
    return json.loads(row[0]) if row else None


def save_court(payload):
    with connection() as db:
        db.execute("INSERT INTO court VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                   (json.dumps(payload, ensure_ascii=False),))


def create_session(session_id, payload):
    stamp = now()
    with connection() as db:
        db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)",
                   (session_id, "preparing", json.dumps(payload, ensure_ascii=False), stamp, stamp))
    return get_session(session_id)


def decode_session(row):
    return {**json.loads(row["payload"]), "id": row["id"], "status": row["status"],
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


def get_session(session_id):
    with connection() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        raise KeyError(session_id)
    return decode_session(row)


def list_sessions():
    with connection() as db:
        rows = db.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100").fetchall()
    return [decode_session(row) for row in rows]


def update_session(session_id, **changes):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        payload = json.loads(row["payload"])
        status = changes.pop("status", row["status"])
        payload.update(changes)
        db.execute("UPDATE sessions SET status=?,payload=?,updated_at=? WHERE id=?",
                   (status, json.dumps(payload, ensure_ascii=False), now(), session_id))
    return get_session(session_id)


def recover_sessions():
    with connection() as db:
        rows = db.execute("SELECT id FROM sessions WHERE status IN ('preparing','running','reconnecting','stopping')").fetchall()
    for row in rows:
        update_session(row[0], status="interrupted", message="服务重启，会话已中断；已保存的数据仍可下载。")
