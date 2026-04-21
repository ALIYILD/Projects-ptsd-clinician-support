from __future__ import annotations

from pathlib import Path

from ptsd_support.db.schema import connect


def list_guidelines(db_path: str | Path) -> list[dict]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT guideline_key, source_name, title, organization, version_label,
                   publication_date, review_date, source_url, jurisdiction, status
            FROM guidelines
            ORDER BY publication_date DESC, id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_guideline_recommendations(
    db_path: str | Path,
    *,
    clinical_domain: str | None = None,
    modality: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conn = connect(db_path)
    try:
        clauses = ["1=1"]
        params: list[object] = []
        if clinical_domain:
            clauses.append("gr.clinical_domain = ?")
            params.append(clinical_domain)
        if modality:
            clauses.append("gr.modality = ?")
            params.append(modality)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT
                g.guideline_key,
                g.title AS guideline_title,
                g.organization,
                gr.recommendation_key,
                gr.clinical_domain,
                gr.modality,
                gr.population,
                gr.recommendation_text,
                gr.strength,
                gr.evidence_basis,
                gr.caution_notes
            FROM guideline_recommendations gr
            JOIN guidelines g ON g.id = gr.guideline_id
            WHERE {' AND '.join(clauses)}
            ORDER BY g.organization, gr.clinical_domain, gr.id
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
