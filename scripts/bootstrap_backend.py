from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(root / "src"))

    db_path = env.get("PTSD_SUPPORT_DB_PATH", "data/processed/ptsd_support.db")
    guideline_seed = env.get("PTSD_SUPPORT_GUIDELINE_SEED", "data/raw/guidelines/ptsd_guidelines.json")
    host = env.get("PTSD_SUPPORT_HOST", "127.0.0.1")
    port = env.get("PTSD_SUPPORT_PORT", "8080")
    audit_log = env.get("PTSD_SUPPORT_AUDIT_LOG", "data/processed/audit.jsonl")
    request_log = env.get("PTSD_SUPPORT_REQUEST_LOG", "data/processed/requests.jsonl")

    subprocess.run(
        [sys.executable, "scripts/ingest_guidelines.py", "--db", db_path, "--seed", guideline_seed],
        check=True,
        cwd=root,
        env=env,
    )
    subprocess.run(
        [sys.executable, "scripts/run_server.py", "--db", db_path, "--host", host, "--port", port, "--audit-log", audit_log, "--request-log", request_log],
        check=True,
        cwd=root,
        env=env,
    )


if __name__ == "__main__":
    main()
