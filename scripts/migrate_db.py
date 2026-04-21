from __future__ import annotations

import argparse
from pathlib import Path

from ptsd_support.db.migrations import run_migrations


def main() -> None:
    parser = argparse.ArgumentParser(description="Run database migrations.")
    parser.add_argument("--db", required=True, help="Path to database file.")
    args = parser.parse_args()
    run_migrations(Path(args.db).expanduser().resolve())
    print(f"Migrations applied to {Path(args.db).expanduser().resolve()}")


if __name__ == "__main__":
    main()
