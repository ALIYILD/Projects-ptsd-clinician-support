from __future__ import annotations

import argparse
from pathlib import Path

from ptsd_support.ingest.guidelines import ingest_guideline_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PTSD guideline seed data into SQLite.")
    parser.add_argument("--db", required=True, help="Path to SQLite database file.")
    parser.add_argument(
        "--seed",
        default="data/raw/guidelines/ptsd_guidelines.json",
        help="Path to guideline seed JSON file.",
    )
    args = parser.parse_args()

    result = ingest_guideline_seed(
        Path(args.db).expanduser().resolve(),
        Path(args.seed).expanduser().resolve(),
    )
    print(result)


if __name__ == "__main__":
    main()
