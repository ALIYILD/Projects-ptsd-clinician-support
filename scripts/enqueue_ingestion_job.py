from __future__ import annotations

import argparse
from pathlib import Path

from ptsd_support.services.jobs import enqueue_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Enqueue a background ingestion job.")
    parser.add_argument("--queue-dir", default="data/processed/jobs", help="Job queue directory.")
    parser.add_argument("--job-type", choices=["ingest_literature", "ingest_guidelines"], required=True)
    parser.add_argument("--db", required=True, help="Target database path.")
    parser.add_argument("--inputs", nargs="*", help="Input CSV files for literature ingestion.")
    parser.add_argument("--seed", help="Guideline seed path for guideline ingestion.")
    args = parser.parse_args()

    payload = {"db_path": str(Path(args.db).expanduser().resolve())}
    if args.job_type == "ingest_literature":
        payload["inputs"] = [str(Path(item).expanduser().resolve()) for item in (args.inputs or [])]
    if args.job_type == "ingest_guidelines":
        payload["seed_path"] = str(Path(args.seed).expanduser().resolve())

    job = enqueue_job(args.queue_dir, args.job_type, payload)
    print(job)


if __name__ == "__main__":
    main()
