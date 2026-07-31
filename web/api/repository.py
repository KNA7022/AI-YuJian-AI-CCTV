from datetime import datetime

from .db import decode_json, encode_json, get_connection
from .models import ArtifactRecord, JobConfig, JobRecord


def _now() -> str:
    return datetime.utcnow().isoformat()


def row_to_job(row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        video_path=row["video_path"],
        template_frame_path=row["template_frame_path"],
        calibration_points=decode_json(row["calibration_points"]),
        config_json=JobConfig.model_validate(decode_json(row["config_json"])),
        output_dir=row["output_dir"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        updated_at=row["updated_at"],
    )


def create_job(job_id: str, name: str, video_path: str, output_dir: str, config: JobConfig) -> JobRecord:
    now = _now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, name, status, video_path, template_frame_path, calibration_points,
                config_json, output_dir, error_message, created_at, started_at, finished_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                name,
                "draft",
                video_path,
                None,
                None,
                encode_json(config.model_dump()),
                output_dir,
                None,
                now,
                None,
                None,
                now,
            ),
        )
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_job(row)


def update_job(job_id: str, **fields) -> JobRecord:
    if not fields:
        return get_job(job_id)
    fields["updated_at"] = _now()
    if "config_json" in fields and not isinstance(fields["config_json"], str):
        fields["config_json"] = encode_json(fields["config_json"])
    if "calibration_points" in fields and fields["calibration_points"] is not None and not isinstance(fields["calibration_points"], str):
        fields["calibration_points"] = encode_json(fields["calibration_points"])
    assignments = ", ".join(f"{key} = ?" for key in fields.keys())
    values = list(fields.values()) + [job_id]
    with get_connection() as connection:
        connection.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_job(row)


def get_job(job_id: str) -> JobRecord:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    return row_to_job(row)


def list_jobs() -> list[JobRecord]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [row_to_job(row) for row in rows]


def list_jobs_by_status(status: str) -> list[JobRecord]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC", (status,)).fetchall()
    return [row_to_job(row) for row in rows]


def upsert_artifacts(job_id: str, artifacts: dict[str, tuple[str, str]]) -> None:
    now = _now()
    with get_connection() as connection:
        connection.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
        for artifact_type, (path, mime_type) in artifacts.items():
            connection.execute(
                "INSERT INTO artifacts (job_id, type, path, mime_type, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, artifact_type, path, mime_type, now),
            )


def list_artifacts(job_id: str) -> list[ArtifactRecord]:
    with get_connection() as connection:
        rows = connection.execute("SELECT job_id, type, path, mime_type FROM artifacts WHERE job_id = ?", (job_id,)).fetchall()
    return [ArtifactRecord(**dict(row)) for row in rows]


def delete_job_records(job_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
        cursor = connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    if cursor.rowcount == 0:
        raise KeyError(job_id)
