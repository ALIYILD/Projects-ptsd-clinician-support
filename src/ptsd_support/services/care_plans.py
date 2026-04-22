from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ptsd_support.db.schema import connect


CARE_PLAN_RED_FLAG_BLOCKERS = {
    "suicidality": "Immediate suicide-risk review is required before a care plan can be drafted.",
    "homicidality": "Violence-risk review is required before a care plan can be drafted.",
    "psychosis": "Psychosis or delirium concerns require urgent specialist review before planning.",
    "mania": "Mania or activation concerns require urgent clinician review before planning.",
}

CARE_PLAN_CONTRAINDICATION_BLOCKERS = {
    "acute_safety": "Acute safety concerns block deterministic care-plan generation.",
    "legal_or_consent_context": "Consent, guardianship, or forensic issues require direct clinician planning.",
}

HOME_TASK_RED_FLAG_BLOCKERS = {
    **CARE_PLAN_RED_FLAG_BLOCKERS,
    "severe_dissociation_or_impaired_capacity": (
        "Severe dissociation or decisional-capacity concerns block between-session task generation."
    ),
    "abuse_neglect_or_exploitation": (
        "Active safeguarding concerns block between-session task generation until reviewed."
    ),
}

HOME_TASK_CONTRAINDICATION_BLOCKERS = {
    **CARE_PLAN_CONTRAINDICATION_BLOCKERS,
    "trauma_treatment_readiness": "Readiness concerns block independent trauma-focused homework.",
}

SAFETY_DISCLAIMER = (
    "Clinician review only. These outputs are support drafts, not patient-facing instructions, "
    "and must not replace risk assessment, crisis workflows, or clinical judgment."
)

HOME_TASK_DISCLAIMER = (
    "Between-session tasks should be assigned only after the clinician confirms stability, "
    "readiness, literacy, access, and a stop plan if distress escalates."
)


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


def _list_codes(items: list[dict[str, Any]] | None, key: str) -> list[str]:
    if not items:
        return []
    codes = []
    for item in items:
        value = item.get(key)
        if isinstance(value, str) and value not in codes:
            codes.append(value)
    return codes


def _case_value(case_context: dict[str, Any], key: str) -> bool:
    value = case_context.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "present"}
    return bool(value)


def _collect_blockers(
    case_evaluation: dict[str, Any],
    *,
    red_flag_map: dict[str, str],
    contraindication_map: dict[str, str],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for code in _list_codes(case_evaluation.get("red_flags"), "code"):
        if code in red_flag_map:
            blockers.append({"type": "red_flag", "code": code, "reason": red_flag_map[code]})
    for code in _list_codes(case_evaluation.get("contraindications"), "category"):
        if code in contraindication_map:
            blockers.append({"type": "contraindication", "code": code, "reason": contraindication_map[code]})
    return blockers


def _phase_focus(case_context: dict[str, Any]) -> list[str]:
    symptoms = {str(item).lower() for item in (case_context.get("symptoms") or [])}
    focus = ["sleep regulation", "grounding", "routine restoration"]
    if "nightmares" in symptoms or _case_value(case_context, "nightmares"):
        focus.append("nightmare monitoring")
    if "avoidance" in symptoms:
        focus.append("avoidance mapping")
    if "hypervigilance" in symptoms:
        focus.append("arousal reduction")
    if "dissociation" in symptoms:
        focus.append("orientation skills")
    return focus


def _build_phases(case_context: dict[str, Any]) -> list[dict[str, Any]]:
    focus = _phase_focus(case_context)
    return [
        {
            "phase": 1,
            "name": "Stabilization And Safety",
            "timeline": "Sessions 1-2",
            "goals": [
                "Confirm immediate safety, crisis contacts, and escalation thresholds.",
                "Review sleep, substance use, and environmental barriers affecting stability.",
                "Introduce one or two grounding or regulation strategies before deeper trauma work.",
            ],
            "clinician_actions": [
                "Review red flags, contraindications, and missing information before activating the plan.",
                "Set a stop rule for escalating distress, dissociation, or worsening insomnia.",
                f"Prioritize early focus areas: {', '.join(focus)}.",
            ],
        },
        {
            "phase": 2,
            "name": "Skill Building And Readiness",
            "timeline": "Sessions 3-5",
            "goals": [
                "Build coping consistency with brief, repeatable regulation practice.",
                "Clarify triggers, patterns of avoidance, and situations linked to symptom spikes.",
                "Assess readiness for trauma-focused interventions and need for pacing adjustments.",
            ],
            "clinician_actions": [
                "Review adherence barriers between sessions and simplify tasks if completion drops.",
                "Use symptom tracking to decide whether pacing should stay supportive or become trauma-focused.",
                "Re-check dissociation, sleep disruption, and substance use before increasing task intensity.",
            ],
        },
        {
            "phase": 3,
            "name": "Trauma Processing And Relapse Prevention",
            "timeline": "Sessions 6+",
            "goals": [
                "Advance to trauma-focused work only if safety and readiness remain acceptable.",
                "Link treatment targets to functional recovery at home, work, and relationships.",
                "Create a relapse-prevention plan for triggers, anniversaries, and missed-session periods.",
            ],
            "clinician_actions": [
                "Document the rationale for starting, pausing, or deferring trauma processing.",
                "Review response to exposure or cognitive work and step back if distress becomes destabilizing.",
                "End each block with a maintenance plan covering warning signs and follow-up supports.",
            ],
        },
    ]


def _build_home_tasks(case_context: dict[str, Any]) -> list[dict[str, str]]:
    tasks = [
        {
            "title": "Daily grounding practice",
            "schedule": "Once or twice daily for 2-5 minutes",
            "instructions": "Use a brief grounding or paced-breathing exercise rehearsed in session.",
            "clinical_purpose": "Improves recall of regulation skills during symptom spikes.",
        },
        {
            "title": "Trigger and distress log",
            "schedule": "Complete after noticeable stress spikes",
            "instructions": "Record trigger, distress level, body cues, coping step used, and whether symptoms settled.",
            "clinical_purpose": "Gives the clinician concrete data for pacing and formulation.",
        },
    ]

    symptoms = {str(item).lower() for item in (case_context.get("symptoms") or [])}
    if "nightmares" in symptoms or _case_value(case_context, "nightmares"):
        tasks.append(
            {
                "title": "Sleep and nightmare tracking",
                "schedule": "Each morning",
                "instructions": "Record sleep duration, awakenings, nightmare presence, and next-day fatigue.",
                "clinical_purpose": "Supports review of sleep disruption before changing care intensity.",
            }
        )
    elif "avoidance" in symptoms:
        tasks.append(
            {
                "title": "Avoidance map",
                "schedule": "Add one example on three separate days",
                "instructions": "Write down situations, thoughts, or places avoided and the short-term relief gained.",
                "clinical_purpose": "Helps the clinician identify exposure targets without assigning exposure independently.",
            }
        )
    else:
        tasks.append(
            {
                "title": "Recovery routine check-in",
                "schedule": "Three times this week",
                "instructions": "Track sleep timing, meals, movement, and social contact in a simple checklist.",
                "clinical_purpose": "Shows whether daily structure is improving enough to support further treatment work.",
            }
        )
    return tasks


def build_care_plan(
    *,
    case_context: dict[str, Any] | None = None,
    case_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_context = case_context or {}
    case_evaluation = case_evaluation or {}
    blockers = _collect_blockers(
        case_evaluation,
        red_flag_map=CARE_PLAN_RED_FLAG_BLOCKERS,
        contraindication_map=CARE_PLAN_CONTRAINDICATION_BLOCKERS,
    )
    missing_information = list(case_evaluation.get("missing_information") or [])
    status = "blocked" if blockers else "review"
    phases = [] if blockers else _build_phases(case_context)
    between_session_tasks = [] if blockers else _build_home_tasks(case_context)

    return {
        "status": status,
        "review_only": True,
        "clinician_review_required": True,
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "missing_information": missing_information,
        "blockers": blockers,
        "phases": phases,
        "between_session_tasks": between_session_tasks,
        "plan_summary": (
            "Care-plan drafting is blocked pending direct clinician review."
            if blockers
            else "Phased PTSD support plan drafted for clinician review with between-session task options."
        ),
    }


def build_home_task_plan(
    *,
    case_context: dict[str, Any] | None = None,
    case_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_context = case_context or {}
    case_evaluation = case_evaluation or {}
    blockers = _collect_blockers(
        case_evaluation,
        red_flag_map=HOME_TASK_RED_FLAG_BLOCKERS,
        contraindication_map=HOME_TASK_CONTRAINDICATION_BLOCKERS,
    )
    tasks = [] if blockers else _build_home_tasks(case_context)

    return {
        "status": "blocked" if blockers else "review",
        "review_only": True,
        "clinician_review_required": True,
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "task_disclaimer": HOME_TASK_DISCLAIMER,
        "blockers": blockers,
        "tasks": tasks,
        "recommended_monitoring": [] if blockers else ["distress 0-10 rating", "sleep changes", "dissociation warning signs"],
    }


def generate_care_plan(
    case: dict[str, Any],
    case_evaluation: dict[str, Any],
    support_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phased = build_care_plan(case_context=case, case_evaluation=case_evaluation)
    tasks = build_home_task_plan(case_context=case, case_evaluation=case_evaluation)
    return {
        "status": "blocked" if phased["status"] == "blocked" or tasks["status"] == "blocked" else "draft",
        "review_only": True,
        "clinician_review_required": True,
        "support_domains": (support_plan or {}).get("domains", []),
        "blockers": phased["blockers"] or tasks["blockers"],
        "phased_plan": phased.get("phases", []),
        "home_tasks": tasks.get("tasks", []),
        "disclaimer": SAFETY_DISCLAIMER,
        "task_disclaimer": HOME_TASK_DISCLAIMER,
        "plan_summary": phased.get("plan_summary"),
    }


def save_care_plan(
    db_path: str | Path,
    *,
    case_key: str,
    plan_type: str,
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
            INSERT INTO care_plans(case_id, plan_type, status, payload_json, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                case_row["id"],
                plan_type,
                payload.get("status", "draft"),
                json.dumps(payload, ensure_ascii=True),
                created_by,
            ),
        )
        conn.commit()
        row = _fetch_one_as_dict(
            conn,
            "SELECT * FROM care_plans WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_row["id"],),
        )
        assert row is not None
        return _decode_payload_row(row)
    finally:
        conn.close()


def list_care_plans(
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
            "SELECT * FROM care_plans WHERE case_id = ? ORDER BY created_at DESC, id DESC",
            (case_row["id"],),
        )
        return [_decode_payload_row(row) for row in rows]
    finally:
        conn.close()
