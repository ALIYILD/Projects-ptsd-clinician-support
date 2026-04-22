from __future__ import annotations

import json
from pathlib import Path

from ptsd_support.db.adapter import fetch_scalar
from ptsd_support.db.schema import connect, initialize_database


def ingest_guideline_seed(db_path: str | Path, seed_path: str | Path) -> dict[str, int]:
    initialize_database(db_path)
    conn = connect(db_path)
    seed_file = Path(seed_path)
    payload = json.loads(seed_file.read_text(encoding="utf-8"))
    guideline_count = 0
    recommendation_count = 0
    try:
        condition_id = fetch_scalar(conn, "SELECT id FROM conditions WHERE slug = 'ptsd'")
        if condition_id is None:
            raise LookupError("Expected PTSD condition row")
        condition_id = int(condition_id)
        for item in payload.get("guidelines", []):
            conn.execute(
                """
                INSERT INTO guidelines(
                    condition_id, guideline_key, source_name, title, organization,
                    version_label, publication_date, review_date, source_url,
                    jurisdiction, status, source_file_path, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    condition_id,
                    item.get("guideline_key"),
                    item.get("source_name"),
                    item.get("title"),
                    item.get("organization"),
                    item.get("version_label"),
                    item.get("publication_date"),
                    item.get("review_date"),
                    item.get("source_url"),
                    item.get("jurisdiction"),
                    item.get("status", "active"),
                    str(seed_file),
                    item.get("summary"),
                ),
            )
            guideline_id = fetch_scalar(
                conn,
                "SELECT id FROM guidelines WHERE guideline_key = ?",
                (item.get("guideline_key"),),
            )
            if guideline_id is None:
                raise LookupError(f"Expected guideline row for {item.get('guideline_key')}")
            guideline_id = int(guideline_id)
            guideline_count += 1
            for rec in item.get("recommendations", []):
                conn.execute(
                    """
                    INSERT INTO guideline_recommendations(
                        guideline_id, recommendation_key, clinical_domain, population,
                        recommendation_text, modality, strength, evidence_basis,
                        notes_json, caution_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guideline_id,
                        rec.get("recommendation_key"),
                        rec.get("clinical_domain"),
                        rec.get("population"),
                        rec.get("recommendation_text"),
                        rec.get("modality"),
                        rec.get("strength"),
                        rec.get("evidence_basis"),
                        rec.get("notes_json"),
                        rec.get("caution_notes"),
                    ),
                )
                recommendation_count += 1
        conn.commit()
        return {"guidelines": guideline_count, "recommendations": recommendation_count}
    finally:
        conn.close()
