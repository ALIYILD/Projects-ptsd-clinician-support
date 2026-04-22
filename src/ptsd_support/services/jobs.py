from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ptsd_support.db.schema import connect, initialize_database
from ptsd_support.ingest.guidelines import ingest_guideline_seed
from ptsd_support.ingest.literature import InputFile, infer_source_name, ingest_csvs


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_job_dirs(queue_dir: str | Path) -> tuple[Path, Path, Path, Path]:
    root = Path(queue_dir)
    pending = root / "pending"
    running = root / "running"
    done = root / "done"
    failed = root / "failed"
    for path in (pending, running, done, failed):
        path.mkdir(parents=True, exist_ok=True)
    return pending, running, done, failed


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        raise LookupError("Expected job row")
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _persist_job_status(
    db_path: str | Path | None,
    *,
    job_id: str,
    job_type: str,
    status: str,
    payload: dict[str, Any],
    queue_path: str | None,
    requested_by: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    result: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> None:
    if not db_path:
        return
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO job_runs(
                job_id, job_type, status, queue_path, payload_json, requested_by,
                started_at, finished_at, result_json, error_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status = excluded.status,
                queue_path = excluded.queue_path,
                payload_json = excluded.payload_json,
                requested_by = COALESCE(excluded.requested_by, job_runs.requested_by),
                started_at = COALESCE(excluded.started_at, job_runs.started_at),
                finished_at = COALESCE(excluded.finished_at, job_runs.finished_at),
                result_json = COALESCE(excluded.result_json, job_runs.result_json),
                error_text = COALESCE(excluded.error_text, job_runs.error_text)
            """,
            (
                job_id,
                job_type,
                status,
                queue_path,
                json.dumps(payload, ensure_ascii=True),
                requested_by,
                started_at,
                finished_at,
                json.dumps(result, ensure_ascii=True) if result is not None else None,
                error_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def enqueue_job(
    queue_dir: str | Path,
    job_type: str,
    payload: dict[str, Any],
    *,
    requested_by: str | None = None,
) -> dict[str, Any]:
    pending, _, _, _ = ensure_job_dirs(queue_dir)
    job = {
        "job_id": str(uuid.uuid4()),
        "job_type": job_type,
        "payload": payload,
        "status": "pending",
        "created_at": _utcnow(),
        "requested_by": requested_by,
    }
    path = pending / f"{job['created_at'].replace(':', '-')}__{job['job_id']}.json"
    path.write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    _persist_job_status(
        payload.get("db_path"),
        job_id=job["job_id"],
        job_type=job_type,
        status="pending",
        payload=payload,
        queue_path=str(path),
        requested_by=requested_by,
    )
    return job


def process_next_job(queue_dir: str | Path) -> dict[str, Any] | None:
    pending, running, done, failed = ensure_job_dirs(queue_dir)
    jobs = sorted(pending.glob("*.json"))
    if not jobs:
        return None
    path = jobs[0]
    job = json.loads(path.read_text(encoding="utf-8"))
    running_path = running / path.name
    running_path.write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    path.unlink()
    started_at = _utcnow()
    job["status"] = "running"
    job["started_at"] = started_at
    running_path.write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    _persist_job_status(
        job["payload"].get("db_path"),
        job_id=job["job_id"],
        job_type=job["job_type"],
        status="running",
        payload=job["payload"],
        queue_path=str(running_path),
        requested_by=job.get("requested_by"),
        started_at=started_at,
    )
    try:
        result = _dispatch(job)
        job["status"] = "done"
        job["finished_at"] = _utcnow()
        job["result"] = result
        target = done / running_path.name
        _persist_job_status(
            job["payload"].get("db_path"),
            job_id=job["job_id"],
            job_type=job["job_type"],
            status="done",
            payload=job["payload"],
            queue_path=str(target),
            requested_by=job.get("requested_by"),
            started_at=job.get("started_at"),
            finished_at=job["finished_at"],
            result=result,
        )
    except Exception as exc:
        job["status"] = "failed"
        job["finished_at"] = _utcnow()
        job["error"] = str(exc)
        target = failed / running_path.name
        _persist_job_status(
            job["payload"].get("db_path"),
            job_id=job["job_id"],
            job_type=job["job_type"],
            status="failed",
            payload=job["payload"],
            queue_path=str(target),
            requested_by=job.get("requested_by"),
            started_at=job.get("started_at"),
            finished_at=job["finished_at"],
            error_text=job["error"],
        )
    target.write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    running_path.unlink()
    return job


def get_job(db_path: str | Path, job_id: str) -> dict[str, Any] | None:
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT job_id, job_type, status, queue_path, payload_json, requested_by,
                   created_at, started_at, finished_at, result_json, error_text
            FROM job_runs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        payload = _row_to_dict(row)
        payload["payload"] = json.loads(payload.pop("payload_json"))
        if payload.get("result_json"):
            payload["result"] = json.loads(payload.pop("result_json"))
        else:
            payload.pop("result_json", None)
        return payload
    finally:
        conn.close()


def list_jobs(
    db_path: str | Path,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if status:
            rows = conn.execute(
                """
                SELECT job_id, job_type, status, queue_path, payload_json, requested_by,
                       created_at, started_at, finished_at, result_json, error_text
                FROM job_runs
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT job_id, job_type, status, queue_path, payload_json, requested_by,
                       created_at, started_at, finished_at, result_json, error_text
                FROM job_runs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            payload = _row_to_dict(row)
            payload["payload"] = json.loads(payload.pop("payload_json"))
            if payload.get("result_json"):
                payload["result"] = json.loads(payload.pop("result_json"))
            else:
                payload.pop("result_json", None)
            items.append(payload)
        return items
    finally:
        conn.close()


def _dispatch(job: dict[str, Any]) -> dict[str, Any]:
    payload = job["payload"]
    job_type = job["job_type"]
    if job_type == "ingest_literature":
        inputs = [
            InputFile(path=Path(item).expanduser().resolve(), source_name=infer_source_name(Path(item)))
            for item in payload["inputs"]
        ]
        ingest_csvs(payload["db_path"], inputs)
        return {"db_path": payload["db_path"], "inputs": payload["inputs"], "ingested_files": len(inputs)}
    if job_type == "ingest_guidelines":
        return ingest_guideline_seed(payload["db_path"], payload["seed_path"])
    raise ValueError(f"Unsupported job type: {job_type}")
