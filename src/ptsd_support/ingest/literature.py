from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ptsd_support.db.adapter import DBConnection, fetch_scalar, insert_and_get_id
from ptsd_support.db.schema import connect, initialize_database


@dataclass
class InputFile:
    path: Path
    source_name: str


def normalize_title(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def parse_bool(value: str) -> int | None:
    if value is None or value == "":
        return None
    lowered = str(value).strip().lower()
    if lowered in {"y", "yes", "true", "1"}:
        return 1
    if lowered in {"n", "no", "false", "0"}:
        return 0
    return None


def parse_int(value: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def infer_source_name(path: Path) -> str:
    name = path.name.lower()
    if "pubmed" in name:
        return "pubmed"
    if "europepmc" in name:
        return "europepmc"
    return "unknown"


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    normalized = normalized.removeprefix("https://doi.org/")
    normalized = normalized.removeprefix("http://doi.org/")
    normalized = normalized.removeprefix("doi:")
    return normalized or None


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_rows(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def register_source(conn: DBConnection, source_name: str) -> None:
    conn.execute(
        """
        INSERT INTO sources(name, source_type, description)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO NOTHING
        """,
        (source_name, "literature_export", f"Ingested literature source: {source_name}"),
    )


def register_source_file(conn: DBConnection, path: Path) -> int:
    sha256 = compute_sha256(path)
    row_count = count_rows(path)
    conn.execute(
        """
        INSERT INTO source_files(path, file_name, sha256, format, row_count, parser_version)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            sha256 = excluded.sha256,
            row_count = excluded.row_count,
            parser_version = excluded.parser_version,
            imported_at = CURRENT_TIMESTAMP
        """,
        (str(path), path.name, sha256, "csv", row_count, "0.1.0"),
    )
    source_file_id = fetch_scalar(conn, "SELECT id FROM source_files WHERE path = ?", (str(path),))
    if source_file_id is None:
        raise LookupError(f"Expected source_files row for {path}")
    return int(source_file_id)


def derive_canonical_key(row: dict[str, str], source_name: str) -> tuple[str, str | None, str | None]:
    doi = normalize_doi(row.get("doi"))
    pmid = (row.get("pmid") or row.get("id") or "").strip() or None
    native_id = (row.get("id") or row.get("pmid") or "").strip() or None
    if doi:
        return f"doi:{doi}", pmid, doi
    if source_name == "pubmed" and pmid:
        return f"pmid:{pmid}", pmid, doi
    if pmid and pmid.isdigit():
        return f"pmid:{pmid}", pmid, doi
    if native_id:
        return f"{source_name}:{native_id}", pmid, doi
    return f"title:{normalize_title(row.get('title') or '')}", pmid, doi


def get_or_create_article(conn: DBConnection, row: dict[str, str], source_name: str) -> int:
    payload_pmid = (row.get("pmid") or row.get("id") or "").strip() or None
    canonical_key, pmid, doi = derive_canonical_key(row, source_name)
    title = row.get("title") or ""
    normalized_title = normalize_title(title)
    journal = row.get("journal")
    publication_year = parse_int(row.get("pub_year"))
    publication_date = row.get("first_publication_date")
    is_open_access = parse_bool(row.get("is_open_access"))
    has_fulltext_link = parse_bool(row.get("has_pdf")) or parse_bool(row.get("in_pmc"))

    existing = None
    if doi:
        existing = conn.execute("SELECT id FROM articles WHERE doi = ?", (doi,)).fetchone()
    if existing is None and pmid:
        existing = conn.execute("SELECT id FROM articles WHERE pmid = ?", (pmid,)).fetchone()
    if existing is None:
        existing = conn.execute("SELECT id FROM articles WHERE canonical_key = ?", (canonical_key,)).fetchone()

    if existing is None:
        article_id = insert_and_get_id(
            conn,
            """
            INSERT INTO articles (
                canonical_key, pmid, doi, title, authors, journal, publication_year,
                publication_date, is_open_access, has_fulltext_link, normalized_title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_key,
                pmid or payload_pmid,
                doi,
                title,
                row.get("authors"),
                journal,
                publication_year,
                publication_date,
                is_open_access,
                has_fulltext_link,
                normalized_title,
            ),
        )
    else:
        article_id = int(existing["id"])
        conn.execute(
            """
            UPDATE articles
            SET
                pmid = COALESCE(pmid, ?),
                doi = COALESCE(doi, ?),
                title = CASE
                    WHEN title = '' AND ? <> '' THEN ?
                    ELSE title
                END,
                authors = COALESCE(authors, ?),
                journal = COALESCE(journal, ?),
                publication_year = COALESCE(publication_year, ?),
                publication_date = COALESCE(publication_date, ?),
                is_open_access = COALESCE(is_open_access, ?),
                has_fulltext_link = COALESCE(has_fulltext_link, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                pmid or payload_pmid,
                doi,
                title,
                title,
                row.get("authors"),
                journal,
                publication_year,
                publication_date,
                is_open_access,
                has_fulltext_link,
                article_id,
            ),
        )
    return article_id


def replace_article_authors(conn: DBConnection, article_id: int, authors_value: str | None) -> None:
    if not authors_value:
        return
    existing = fetch_scalar(
        conn,
        "SELECT COUNT(*) AS count FROM article_authors WHERE article_id = ?",
        (article_id,),
    )
    if existing is None:
        raise LookupError(f"Expected article_authors count for article {article_id}")
    existing = int(existing)
    if existing:
        return
    authors = [part.strip() for part in authors_value.split(",") if part.strip()]
    for idx, author in enumerate(authors, start=1):
        conn.execute(
            """
            INSERT INTO article_authors(article_id, author_ordinal, display_name)
            VALUES (?, ?, ?)
            """,
            (article_id, idx, author),
        )


def replace_publication_types(conn: DBConnection, article_id: int, value: str | None) -> None:
    if not value:
        return
    existing = fetch_scalar(
        conn,
        "SELECT COUNT(*) AS count FROM article_publication_types WHERE article_id = ?",
        (article_id,),
    )
    if existing is None:
        raise LookupError(f"Expected article_publication_types count for article {article_id}")
    existing = int(existing)
    if existing:
        return
    parts = [part.strip() for part in value.replace(";", "|").split("|") if part.strip()]
    for part in parts:
        conn.execute(
            """
            INSERT INTO article_publication_types(article_id, publication_type)
            VALUES (?, ?)
            """,
            (article_id, part),
        )


def tag_article_to_ptsd(conn: DBConnection, article_id: int) -> None:
    condition_id = fetch_scalar(conn, "SELECT id FROM conditions WHERE slug = 'ptsd'")
    if condition_id is None:
        raise LookupError("Expected PTSD condition row")
    conn.execute(
        """
        INSERT INTO article_condition_tags(article_id, condition_id, tag_source)
        VALUES (?, ?, ?)
        ON CONFLICT(article_id, condition_id, tag_source) DO NOTHING
        """,
        (article_id, condition_id, "seed_import"),
    )


def insert_article_source(
    conn: DBConnection,
    article_id: int,
    row: dict[str, str],
    source_name: str,
    source_file_id: int,
) -> None:
    payload = json.dumps(row, ensure_ascii=True)
    native_id = (row.get("id") or row.get("pmid") or "").strip()
    source_subtype = row.get("source")
    conn.execute(
        """
        INSERT INTO article_sources(
            article_id, source_name, source_native_id, source_subtype, source_file_id,
            source_url, raw_row_json, cited_by_count, in_epmc, in_pmc, is_open_access, has_pdf
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_name, source_native_id, source_file_id) DO UPDATE SET
            article_id = excluded.article_id,
            source_subtype = excluded.source_subtype,
            source_url = excluded.source_url,
            raw_row_json = excluded.raw_row_json,
            cited_by_count = excluded.cited_by_count,
            in_epmc = excluded.in_epmc,
            in_pmc = excluded.in_pmc,
            is_open_access = excluded.is_open_access,
            has_pdf = excluded.has_pdf
        """,
        (
            article_id,
            source_name,
            native_id,
            source_subtype,
            source_file_id,
            row.get("europepmc_url"),
            payload,
            parse_int(row.get("cited_by_count")),
            parse_bool(row.get("in_epmc")),
            parse_bool(row.get("in_pmc")),
            parse_bool(row.get("is_open_access")),
            parse_bool(row.get("has_pdf")),
        ),
    )


def ingest_csvs(db_path: str | Path, inputs: Iterable[InputFile]) -> None:
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        for item in inputs:
            register_source(conn, item.source_name)
            source_file_id = register_source_file(conn, item.path)
            row_count = 0
            with item.path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    article_id = get_or_create_article(conn, row, item.source_name)
                    insert_article_source(conn, article_id, row, item.source_name, source_file_id)
                    replace_article_authors(conn, article_id, row.get("authors"))
                    replace_publication_types(conn, article_id, row.get("pub_type"))
                    tag_article_to_ptsd(conn, article_id)
                    row_count += 1
            conn.execute(
                """
                INSERT INTO ingest_runs(source_name, input_path, source_file_id, row_count, finished_at, notes)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (item.source_name, str(item.path), source_file_id, row_count, "csv literature import"),
            )
            conn.commit()
    finally:
        conn.close()
