from __future__ import annotations

import argparse
from pathlib import Path

from ptsd_support.ingest.literature import InputFile, infer_source_name, ingest_csvs


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PTSD literature CSV exports into SQLite.")
    parser.add_argument("--db", required=True, help="Path to SQLite database file.")
    parser.add_argument("--inputs", nargs="+", required=True, help="CSV files to ingest.")
    args = parser.parse_args()

    inputs = []
    for raw in args.inputs:
        path = Path(raw).expanduser().resolve()
        inputs.append(InputFile(path=path, source_name=infer_source_name(path)))

    ingest_csvs(args.db, inputs)
    print(f"Ingested {len(inputs)} file(s) into {Path(args.db).resolve()}")


if __name__ == "__main__":
    main()
