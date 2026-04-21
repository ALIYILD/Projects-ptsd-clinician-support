from __future__ import annotations

import argparse
import time

from ptsd_support.services.jobs import process_next_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Run background ingestion worker.")
    parser.add_argument("--queue-dir", default="data/processed/jobs", help="Job queue directory.")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Polling interval when no jobs are pending.")
    parser.add_argument("--once", action="store_true", help="Process a single job and exit.")
    args = parser.parse_args()

    while True:
        job = process_next_job(args.queue_dir)
        if job:
            print(job)
            if args.once:
                return
            continue
        if args.once:
            print("No jobs pending.")
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
