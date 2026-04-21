from __future__ import annotations

from pathlib import Path

from ptsd_support.db.schema import connect


def _like_query(query: str) -> str:
    return f"%{' '.join(query.strip().lower().split())}%"


def search_titles(db_path: str | Path, query: str, limit: int = 20) -> list[dict]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, doi, journal, publication_year, pmid, canonical_key
            FROM articles
            WHERE normalized_title LIKE ?
            ORDER BY publication_year DESC
            LIMIT ?
            """,
            (_like_query(query), limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def search_articles(
    db_path: str | Path,
    query: str = "",
    *,
    limit: int = 20,
    publication_types: list[str] | None = None,
    source_name: str | None = None,
    open_access_only: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[dict]:
    conn = connect(db_path)
    try:
        clauses = ["1=1"]
        params: list[object] = []

        if query.strip():
            clauses.append("a.normalized_title LIKE ?")
            params.append(_like_query(query))

        if source_name:
            clauses.append(
                """
                EXISTS (
                    SELECT 1
                    FROM article_sources s
                    WHERE s.article_id = a.id
                      AND s.source_name = ?
                )
                """
            )
            params.append(source_name)

        if open_access_only:
            clauses.append("COALESCE(a.is_open_access, 0) = 1")

        if year_from is not None:
            clauses.append("a.publication_year >= ?")
            params.append(year_from)

        if year_to is not None:
            clauses.append("a.publication_year <= ?")
            params.append(year_to)

        if publication_types:
            placeholders = ", ".join("?" for _ in publication_types)
            clauses.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM article_publication_types apt
                    WHERE apt.article_id = a.id
                      AND lower(apt.publication_type) IN ({placeholders})
                )
                """
            )
            params.extend([value.strip().lower() for value in publication_types])

        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT
                a.id,
                a.title,
                a.doi,
                a.pmid,
                a.journal,
                a.publication_year,
                a.publication_date,
                a.is_open_access,
                a.has_fulltext_link,
                a.canonical_key,
                GROUP_CONCAT(DISTINCT apt.publication_type) AS publication_types,
                GROUP_CONCAT(DISTINCT src.source_name) AS sources
            FROM articles a
            LEFT JOIN article_publication_types apt ON apt.article_id = a.id
            LEFT JOIN article_sources src ON src.article_id = a.id
            WHERE {' AND '.join(clauses)}
            GROUP BY a.id
            ORDER BY a.publication_year DESC, a.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_reviews_or_trials(db_path: str | Path, limit: int = 20, query: str = "") -> list[dict]:
    return search_articles(
        db_path,
        query,
        limit=limit,
        publication_types=["review", "clinical trial"],
    )


def get_ingest_summary(db_path: str | Path) -> dict[str, int]:
    conn = connect(db_path)
    try:
        summary = {}
        for table in [
            "articles",
            "article_sources",
            "article_authors",
            "article_publication_types",
            "source_files",
            "ingest_runs",
        ]:
            summary[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return summary
    finally:
        conn.close()
