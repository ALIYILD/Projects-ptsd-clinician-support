from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ptsd_support.db.schema import connect, initialize_database


def _serialize_list(value: Any) -> str:
    return json.dumps(value if isinstance(value, list) else [], ensure_ascii=True)


def _serialize_dict(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=True)


def create_case(db_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        case_key = payload.get("case_key") or str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO patient_cases(
                case_key, patient_id, clinician_id, age, trauma_exposure_summary,
                symptom_duration_weeks, functional_impairment, symptoms_json,
                comorbidities_json, medications_json, flags_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_key,
                payload["patient_id"],
                payload.get("clinician_id"),
                payload.get("age"),
                payload.get("trauma_exposure_summary"),
                payload.get("symptom_duration_weeks"),
                payload.get("functional_impairment"),
                _serialize_list(payload.get("symptoms")),
                _serialize_list(payload.get("comorbidities")),
                _serialize_list(payload.get("medications")),
                _serialize_dict(payload.get("flags")),
                payload.get("status", "open"),
            ),
        )
        conn.commit()
        return get_case_by_key(db_path, case_key)
    finally:
        conn.close()


def get_case_by_key(db_path: str | Path, case_key: str) -> dict[str, Any] | None:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM patient_cases WHERE case_key = ?",
            (case_key,),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        for field in ["symptoms_json", "comorbidities_json", "medications_json", "flags_json"]:
            data[field.removesuffix("_json")] = json.loads(data.pop(field))
        return data
    finally:
        conn.close()


def list_cases(db_path: str | Path, patient_id: str | None = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if patient_id:
            rows = conn.execute(
                "SELECT * FROM patient_cases WHERE patient_id = ? ORDER BY updated_at DESC",
                (patient_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM patient_cases ORDER BY updated_at DESC"
            ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            for field in ["symptoms_json", "comorbidities_json", "medications_json", "flags_json"]:
                data[field.removesuffix("_json")] = json.loads(data.pop(field))
            results.append(data)
        return results
    finally:
        conn.close()


def add_case_review(
    db_path: str | Path,
    case_key: str,
    *,
    reviewer_id: str,
    review_type: str,
    review_status: str,
    note: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        case_row = conn.execute(
            "SELECT id FROM patient_cases WHERE case_key = ?",
            (case_key,),
        ).fetchone()
        if case_row is None:
            raise ValueError(f"Unknown case_key: {case_key}")
        conn.execute(
            """
            INSERT INTO case_reviews(case_id, reviewer_id, review_type, review_status, note, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (case_row["id"], reviewer_id, review_type, review_status, note, _serialize_dict(payload)),
        )
        conn.execute(
            "UPDATE patient_cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (case_row["id"],),
        )
        conn.commit()
        review = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_row["id"],),
        ).fetchone()
        result = dict(review)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result
    finally:
        conn.close()


def list_case_reviews(db_path: str | Path, case_key: str) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        case_row = conn.execute(
            "SELECT id FROM patient_cases WHERE case_key = ?",
            (case_key,),
        ).fetchone()
        if case_row is None:
            return []
        rows = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY created_at DESC, id DESC",
            (case_row["id"],),
        ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            data["payload"] = json.loads(data.pop("payload_json"))
            results.append(data)
        return results
    finally:
        conn.close()


def record_case_recommendation(
    db_path: str | Path,
    case_key: str,
    *,
    recommendation_domain: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        case_row = conn.execute(
            "SELECT id FROM patient_cases WHERE case_key = ?",
            (case_key,),
        ).fetchone()
        if case_row is None:
            raise ValueError(f"Unknown case_key: {case_key}")
        conn.execute(
            """
            INSERT INTO case_recommendation_history(case_id, recommendation_domain, payload_json)
            VALUES (?, ?, ?)
            """,
            (case_row["id"], recommendation_domain, json.dumps(payload, ensure_ascii=True)),
        )
        conn.execute(
            "UPDATE patient_cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (case_row["id"],),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM case_recommendation_history WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_row["id"],),
        ).fetchone()
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result
    finally:
        conn.close()
