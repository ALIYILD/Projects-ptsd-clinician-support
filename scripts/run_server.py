from __future__ import annotations

import argparse
import os
from pathlib import Path
from wsgiref.simple_server import make_server

from ptsd_support.api.app import AppConfig, create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PTSD clinician support backend.")
    parser.add_argument(
        "--db",
        default=os.environ.get("PTSD_SUPPORT_DB_PATH", "data/processed/ptsd_support.db"),
        help="Path to SQLite database.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("PTSD_SUPPORT_HOST", "127.0.0.1"),
        help="Bind host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PTSD_SUPPORT_PORT", "8080")),
        help="Bind port.",
    )
    parser.add_argument(
        "--audit-log",
        default=os.environ.get("PTSD_SUPPORT_AUDIT_LOG", "data/processed/audit.jsonl"),
        help="Path to append-only audit log.",
    )
    parser.add_argument(
        "--request-log",
        default=os.environ.get("PTSD_SUPPORT_REQUEST_LOG", "data/processed/requests.jsonl"),
        help="Path to structured request log.",
    )
    args = parser.parse_args()

    app = create_app(
        AppConfig(
            db_path=Path(args.db).expanduser().resolve(),
            audit_log_path=Path(args.audit_log).expanduser().resolve(),
            request_log_path=Path(args.request_log).expanduser().resolve(),
        )
    )

    with make_server(args.host, args.port, app) as server:
        print(f"Serving on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
