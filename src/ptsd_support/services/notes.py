from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ptsd_support.db.schema import connect


REVIEW_BANNER = (
    "DRAFT FOR CLINICIAN REVIEW ONLY: This note draft is generated from structured inputs, "
    "requires independent verification, and is not a finalized clinical note."
)

MISSING_CONTENT_LINE = "No supporting detail was supplied in the structured inputs."


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


def _decode_payload_row(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    record["payload"] = json.loads(record.pop("payload_json"))
    return record


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return " ".join(str(value).strip().split())


def _clean_items(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = _stringify(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _sentence(value: str) -> str:
    text = value.rstrip(". ")
    return f"{text}." if text else ""


def _titleize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _format_string_list(prefix: str, values: Any) -> list[str]:
    items = _clean_items(_coerce_list(values))
    if not items:
        return []
    return [f"{prefix}: {', '.join(items)}."]


def _format_red_flags(red_flags: Any) -> list[str]:
    lines: list[str] = []
    for flag in _coerce_list(red_flags):
        if not isinstance(flag, dict):
            text = _stringify(flag)
            if text:
                lines.append(_sentence(text))
            continue
        label = _stringify(flag.get("label")) or _titleize(_stringify(flag.get("code")) or "Risk flag")
        severity = _stringify(flag.get("severity"))
        reason = _stringify(flag.get("reason"))
        required_action = _stringify(flag.get("required_action"))
        triggered_by = _clean_items(_coerce_list(flag.get("triggered_by")))

        parts = [label]
        if severity:
            parts[0] = f"{label} ({severity})"
        if reason:
            parts.append(reason)
        if triggered_by:
            parts.append(f"Triggered by: {', '.join(triggered_by)}")
        if required_action:
            parts.append(f"Action: {required_action}")
        lines.append(_sentence("; ".join(parts)))
    return lines


def _format_contraindications(contraindications: Any) -> list[str]:
    lines: list[str] = []
    for item in _coerce_list(contraindications):
        if not isinstance(item, dict):
            text = _stringify(item)
            if text:
                lines.append(_sentence(text))
            continue
        category = _stringify(item.get("category"))
        triggered_by = _clean_items(_coerce_list(item.get("triggered_by")))
        review_only = item.get("review_only")

        parts = []
        if category:
            parts.append(_titleize(category))
        if triggered_by:
            parts.append(f"Triggered by: {', '.join(triggered_by)}")
        if review_only:
            parts.append("Review-only consideration")
        if parts:
            lines.append(_sentence("; ".join(parts)))
    return lines


def _format_support_outputs(outputs: Any) -> list[str]:
    lines: list[str] = []
    for output in _coerce_list(outputs):
        if not isinstance(output, dict):
            text = _stringify(output)
            if text:
                lines.append(_sentence(text))
            continue
        name = _stringify(output.get("name")) or "Unnamed support option"
        modality = _stringify(output.get("modality"))
        evidence_basis = _stringify(output.get("evidence_basis"))
        cautions = _clean_items(_coerce_list(output.get("cautions")))
        guideline_count = len(_coerce_list(output.get("guideline_recommendations")))
        evidence_count = len(_coerce_list(output.get("evidence_cards")))

        parts = [name]
        if modality:
            parts[0] = f"{name} ({modality})"
        if evidence_basis:
            parts.append(evidence_basis)
        parts.append(f"Guideline items: {guideline_count}")
        parts.append(f"Evidence cards: {evidence_count}")
        if cautions:
            parts.append(f"Cautions: {', '.join(cautions)}")
        lines.append(_sentence("; ".join(parts)))
    return lines


def _build_section(heading: str, lines: list[str]) -> dict[str, Any]:
    content = _clean_items(lines)
    if not content:
        content = [MISSING_CONTENT_LINE]
    return {"heading": heading, "content": content}


def _render_note(title: str, sections: list[dict[str, Any]]) -> str:
    blocks = [REVIEW_BANNER, "", title]
    for section in sections:
        blocks.extend(["", section["heading"]])
        blocks.extend(f"- {line}" for line in section["content"])
    return "\n".join(blocks)


def _build_note(title: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    rendered = _render_note(title, sections)
    return {
        "title": title,
        "clinician_review_required": True,
        "review_banner": REVIEW_BANNER,
        "sections": sections,
        "text": rendered,
    }


def draft_assessment_summary(case: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    sections = [
        _build_section(
            "Case Context",
            [
                _sentence(f"Patient ID: {_stringify(case.get('patient_id'))}") if case.get("patient_id") else "",
                _sentence(f"Age: {_stringify(case.get('age'))}") if case.get("age") is not None else "",
                _sentence(f"Trauma exposure summary: {_stringify(case.get('trauma_exposure_summary'))}")
                if case.get("trauma_exposure_summary")
                else "",
                _sentence(f"Symptom duration (weeks): {_stringify(case.get('symptom_duration_weeks'))}")
                if case.get("symptom_duration_weeks") is not None
                else "",
                _sentence(f"Functional impairment: {_stringify(case.get('functional_impairment'))}")
                if case.get("functional_impairment")
                else "",
                *_format_string_list("Symptoms", case.get("symptoms")),
                *_format_string_list("Comorbidities", case.get("comorbidities")),
            ],
        ),
        _build_section(
            "Assessment Summary",
            [
                _sentence(_stringify(evaluation.get("assessment_summary"))),
                _sentence(_stringify(evaluation.get("triage_note"))),
            ],
        ),
        _build_section("Review Flags", _format_red_flags(evaluation.get("red_flags"))),
        _build_section(
            "Information Still Needed",
            [f"Missing information: {', '.join(_clean_items(_coerce_list(evaluation.get('missing_information'))))}."]
            if _clean_items(_coerce_list(evaluation.get("missing_information")))
            else [],
        ),
    ]
    return _build_note("Assessment Summary Draft", sections)


def draft_risk_summary(case: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    case_context_lines = [
        _sentence(f"Trauma exposure summary: {_stringify(case.get('trauma_exposure_summary'))}")
        if case.get("trauma_exposure_summary")
        else "",
        _sentence(f"Functional impairment: {_stringify(case.get('functional_impairment'))}")
        if case.get("functional_impairment")
        else "",
        *_format_string_list("Symptoms", case.get("symptoms")),
    ]
    action_lines = [
        _sentence(_stringify(evaluation.get("triage_note"))),
        *[
            _sentence(_stringify(flag.get("required_action")))
            for flag in _coerce_list(evaluation.get("red_flags"))
            if isinstance(flag, dict) and _stringify(flag.get("required_action"))
        ],
    ]
    sections = [
        _build_section("Risk Context", case_context_lines),
        _build_section("Current Risk Indicators", _format_red_flags(evaluation.get("red_flags"))),
        _build_section(
            "Contraindications And Safety Considerations",
            _format_contraindications(evaluation.get("contraindications")),
        ),
        _build_section("Immediate Review Actions", action_lines),
        _build_section(
            "Information Still Needed",
            [f"Missing information: {', '.join(_clean_items(_coerce_list(evaluation.get('missing_information'))))}."]
            if _clean_items(_coerce_list(evaluation.get("missing_information")))
            else [],
        ),
    ]
    return _build_note("Risk Summary Draft", sections)


def draft_support_plan_summary(
    case: dict[str, Any],
    evaluation: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    domains = _clean_items(_coerce_list(recommendation.get("domains")))
    outputs = _coerce_list(recommendation.get("outputs"))
    sections = [
        _build_section(
            "Care Context",
            [
                _sentence(_stringify(evaluation.get("assessment_summary"))),
                _sentence(_stringify(case.get("functional_impairment")))
                if case.get("functional_impairment")
                else "",
                _sentence(f"Requested support domains: {', '.join(domains)}") if domains else "",
            ],
        ),
        _build_section("Candidate Support Options", _format_support_outputs(outputs)),
        _build_section(
            "Safety And Review Considerations",
            [
                *_format_red_flags(evaluation.get("red_flags")),
                *_format_contraindications(evaluation.get("contraindications")),
                _sentence(_stringify(recommendation.get("note"))),
            ],
        ),
        _build_section(
            "Information Still Needed",
            [f"Missing information: {', '.join(_clean_items(_coerce_list(evaluation.get('missing_information'))))}."]
            if _clean_items(_coerce_list(evaluation.get("missing_information")))
            else [],
        ),
    ]
    return _build_note("Support Plan Summary Draft", sections)


def draft_clinician_note(
    *,
    case: dict[str, Any],
    case_evaluation: dict[str, Any],
    support_plan: dict[str, Any] | None = None,
    differential: dict[str, Any] | None = None,
    care_plan: dict[str, Any] | None = None,
    note_type: str = "assessment",
) -> dict[str, Any]:
    if note_type == "risk":
        return draft_risk_summary(case, case_evaluation)
    if note_type == "support_plan":
        return draft_support_plan_summary(case, case_evaluation, support_plan or {})

    note = draft_assessment_summary(case, case_evaluation)
    if differential:
        note["sections"].append(
            _build_section(
                "Differential Review",
                [
                    f"{item['diagnosis']}: supports={len(item['supporting_features'])}, contradicts={len(item['contradicting_features'])}, missing={len(item['missing_data'])}."
                    for item in differential.get("differentials", [])[:4]
                ],
            )
        )
    if care_plan:
        note["sections"].append(
            _build_section(
                "Care Plan Draft",
                [task.get("task") or task.get("title") for task in care_plan.get("home_tasks", [])[:3]],
            )
        )
    note["title"] = "Assessment Summary Draft" if note_type == "assessment" else f"{_titleize(note_type)} Draft"
    note["note_type"] = note_type
    note["text"] = _render_note(note["title"], note["sections"])
    return note


def save_note_draft(
    db_path: str | Path,
    *,
    case_key: str,
    note_type: str,
    payload: dict[str, Any],
    created_by: str | None = None,
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
            INSERT INTO note_drafts(case_id, note_type, payload_json, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (case_row["id"], note_type, json.dumps(payload, ensure_ascii=True), created_by),
        )
        conn.commit()
        row = _fetch_one_as_dict(
            conn,
            "SELECT * FROM note_drafts WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_row["id"],),
        )
        assert row is not None
        return _decode_payload_row(row)
    finally:
        conn.close()


def list_note_drafts(
    db_path: str | Path,
    *,
    case_key: str,
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
            "SELECT * FROM note_drafts WHERE case_id = ? ORDER BY created_at DESC, id DESC",
            (case_row["id"],),
        )
        return [_decode_payload_row(row) for row in rows]
    finally:
        conn.close()
