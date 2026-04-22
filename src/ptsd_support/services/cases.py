from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ptsd_support.db.schema import connect, initialize_database


def _serialize_list(value: Any) -> str:
    return json.dumps(value if isinstance(value, list) else [], ensure_ascii=True)


def _serialize_dict(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=True)


def _strip_json_suffix(field: str) -> str:
    return field[:-5] if field.endswith("_json") else field


def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "_asdict"):
        return dict(row._asdict())
    raise TypeError(f"Unsupported row type returned by adapter: {type(row)!r}")


def _fetch_one_as_dict(conn: Any, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    return None if row is None else _row_to_dict(row)


def _fetch_all_as_dicts(conn: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [_row_to_dict(row) for row in conn.execute(query, params).fetchall()]


def _decode_json_fields(data: dict[str, Any], *fields: str) -> dict[str, Any]:
    record = dict(data)
    for field in fields:
        record[_strip_json_suffix(field)] = json.loads(record.pop(field))
    return record


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
                comorbidities_json, medications_json, flags_json, status, organization_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload.get("organization_key", "default-org"),
            ),
        )
        conn.commit()
        return get_case_by_key(db_path, case_key)
    finally:
        conn.close()


def get_case_by_key(
    db_path: str | Path,
    case_key: str,
    *,
    organization_keys: set[str] | None = None,
) -> dict[str, Any] | None:
    conn = connect(db_path)
    try:
        if organization_keys:
            placeholders = ", ".join("?" for _ in organization_keys)
            row = _fetch_one_as_dict(
                conn,
                f"SELECT * FROM patient_cases WHERE case_key = ? AND organization_key IN ({placeholders})",
                (case_key, *sorted(organization_keys)),
            )
        else:
            row = _fetch_one_as_dict(
                conn,
                "SELECT * FROM patient_cases WHERE case_key = ?",
                (case_key,),
            )
        if row is None:
            return None
        return _decode_json_fields(row, "symptoms_json", "comorbidities_json", "medications_json", "flags_json")
    finally:
        conn.close()


def list_cases(
    db_path: str | Path,
    patient_id: str | None = None,
    *,
    organization_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if patient_id and organization_keys:
            placeholders = ", ".join("?" for _ in organization_keys)
            rows = _fetch_all_as_dicts(
                conn,
                f"SELECT * FROM patient_cases WHERE patient_id = ? AND organization_key IN ({placeholders}) ORDER BY updated_at DESC",
                (patient_id, *sorted(organization_keys)),
            )
        elif patient_id:
            rows = _fetch_all_as_dicts(
                conn,
                "SELECT * FROM patient_cases WHERE patient_id = ? ORDER BY updated_at DESC",
                (patient_id,),
            )
        elif organization_keys:
            placeholders = ", ".join("?" for _ in organization_keys)
            rows = _fetch_all_as_dicts(
                conn,
                f"SELECT * FROM patient_cases WHERE organization_key IN ({placeholders}) ORDER BY updated_at DESC",
                tuple(sorted(organization_keys)),
            )
        else:
            rows = _fetch_all_as_dicts(
                conn,
                "SELECT * FROM patient_cases ORDER BY updated_at DESC"
            )
        return [
            _decode_json_fields(row, "symptoms_json", "comorbidities_json", "medications_json", "flags_json")
            for row in rows
        ]
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
    organization_keys: set[str] | None = None,
) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        if organization_keys:
            placeholders = ", ".join("?" for _ in organization_keys)
            case_row = _fetch_one_as_dict(
                conn,
                f"SELECT id FROM patient_cases WHERE case_key = ? AND organization_key IN ({placeholders})",
                (case_key, *sorted(organization_keys)),
            )
        else:
            case_row = _fetch_one_as_dict(
                conn,
                "SELECT id FROM patient_cases WHERE case_key = ?",
                (case_key,),
            )
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
        review = _fetch_one_as_dict(
            conn,
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_row["id"],),
        )
        assert review is not None
        return _decode_json_fields(review, "payload_json")
    finally:
        conn.close()


def list_case_reviews(
    db_path: str | Path,
    case_key: str,
    *,
    organization_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if organization_keys:
            placeholders = ", ".join("?" for _ in organization_keys)
            case_row = _fetch_one_as_dict(
                conn,
                f"SELECT id FROM patient_cases WHERE case_key = ? AND organization_key IN ({placeholders})",
                (case_key, *sorted(organization_keys)),
            )
        else:
            case_row = _fetch_one_as_dict(
                conn,
                "SELECT id FROM patient_cases WHERE case_key = ?",
                (case_key,),
            )
        if case_row is None:
            return []
        rows = _fetch_all_as_dicts(
            conn,
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY created_at DESC, id DESC",
            (case_row["id"],),
        )
        return [_decode_json_fields(row, "payload_json") for row in rows]
    finally:
        conn.close()


def record_case_recommendation(
    db_path: str | Path,
    case_key: str,
    *,
    recommendation_domain: str,
    payload: dict[str, Any],
    organization_keys: set[str] | None = None,
) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        if organization_keys:
            placeholders = ", ".join("?" for _ in organization_keys)
            case_row = _fetch_one_as_dict(
                conn,
                f"SELECT id FROM patient_cases WHERE case_key = ? AND organization_key IN ({placeholders})",
                (case_key, *sorted(organization_keys)),
            )
        else:
            case_row = _fetch_one_as_dict(
                conn,
                "SELECT id FROM patient_cases WHERE case_key = ?",
                (case_key,),
            )
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
        row = _fetch_one_as_dict(
            conn,
            "SELECT * FROM case_recommendation_history WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_row["id"],),
        )
        assert row is not None
        return _decode_json_fields(row, "payload_json")
    finally:
        conn.close()
