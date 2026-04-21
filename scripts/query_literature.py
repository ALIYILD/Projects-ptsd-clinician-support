from __future__ import annotations

import argparse
import json
from pathlib import Path

from ptsd_support.services.retrieval import (
    get_ingest_summary,
    list_reviews_or_trials,
    search_articles,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the PTSD literature database.")
    parser.add_argument("--db", required=True, help="Path to SQLite database file.")
    parser.add_argument("--query", default="", help="Title search query.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum rows to return.")
    parser.add_argument(
        "--type",
        action="append",
        dest="publication_types",
        help="Publication type filter. Repeatable. Example: --type review --type 'clinical trial'",
    )
    parser.add_argument("--source", dest="source_name", help="Source filter, e.g. pubmed or europepmc.")
    parser.add_argument("--open-access-only", action="store_true", help="Limit results to open-access articles.")
    parser.add_argument("--year-from", type=int, help="Minimum publication year.")
    parser.add_argument("--year-to", type=int, help="Maximum publication year.")
    parser.add_argument(
        "--reviews-or-trials",
        action="store_true",
        help="Shortcut for review or clinical-trial filtering.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show ingestion summary instead of article rows.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    db_path = Path(args.db).expanduser().resolve()

    if args.summary:
        print(json.dumps(get_ingest_summary(db_path), indent=2, sort_keys=True))
        return

    if args.reviews_or_trials:
        rows = list_reviews_or_trials(db_path, limit=args.limit, query=args.query)
    else:
        rows = search_articles(
            db_path,
            args.query,
            limit=args.limit,
            publication_types=args.publication_types,
            source_name=args.source_name,
            open_access_only=args.open_access_only,
            year_from=args.year_from,
            year_to=args.year_to,
        )
    print(json.dumps(rows, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
