from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ptsd_support.ingest.guidelines import ingest_guideline_seed
from ptsd_support.ingest.literature import InputFile, infer_source_name, ingest_csvs


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_job_dirs(queue_dir: str | Path) -> tuple[Path, Path, Path]:
    root = Path(queue_dir)
    pending = root / "pending"
    done = root / "done"
    failed = root / "failed"
    for path in (pending, done, failed):
        path.mkdir(parents=True, exist_ok=True)
    return pending, done, failed


def enqueue_job(queue_dir: str | Path, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    pending, _, _ = ensure_job_dirs(queue_dir)
    job = {
        "job_id": str(uuid.uuid4()),
        "job_type": job_type,
        "payload": payload,
        "status": "pending",
        "created_at": _utcnow(),
    }
    path = pending / f"{job['created_at'].replace(':', '-')}__{job['job_id']}.json"
    path.write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    return job


def process_next_job(queue_dir: str | Path) -> dict[str, Any] | None:
    pending, done, failed = ensure_job_dirs(queue_dir)
    jobs = sorted(pending.glob("*.json"))
    if not jobs:
        return None
    path = jobs[0]
    job = json.loads(path.read_text(encoding="utf-8"))
    try:
        result = _dispatch(job)
        job["status"] = "done"
        job["finished_at"] = _utcnow()
        job["result"] = result
        target = done / path.name
    except Exception as exc:
        job["status"] = "failed"
        job["finished_at"] = _utcnow()
        job["error"] = str(exc)
        target = failed / path.name
    target.write_text(json.dumps(job, ensure_ascii=True, indent=2), encoding="utf-8")
    path.unlink()
    return job


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
