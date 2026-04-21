from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RED_FLAG_RULES = {
    "suicidality": {
        "severity": "critical",
        "label": "Suicidality",
        "reason": "Self-harm or suicide risk indicators were present.",
        "required_action": "Immediate clinician risk review and crisis workflow.",
        "triggers": ["suicidal_ideation", "suicide_plan", "recent_attempt"],
    },
    "homicidality": {
        "severity": "critical",
        "label": "Homicidality",
        "reason": "Violence or harm-to-others indicators were present.",
        "required_action": "Immediate clinician safety review and escalation protocol.",
        "triggers": ["homicidal_ideation", "violence_risk"],
    },
    "psychosis": {
        "severity": "critical",
        "label": "Psychosis/Delirium Concern",
        "reason": "Psychosis or severe perceptual disturbance indicators were present.",
        "required_action": "Urgent psychiatric or medical review.",
        "triggers": ["psychosis", "hallucinations", "delirium_concern"],
    },
    "mania": {
        "severity": "critical",
        "label": "Mania/Hypomania Concern",
        "reason": "Mania or activation indicators were present.",
        "required_action": "Urgent clinician review before treatment planning.",
        "triggers": ["mania", "hypomania"],
    },
    "severe_dissociation_or_impaired_capacity": {
        "severity": "high",
        "label": "Severe Dissociation / Capacity Concern",
        "reason": "Severe dissociation or decisional-capacity impairment indicators were present.",
        "required_action": "Pause trauma-processing planning and review stability.",
        "triggers": ["severe_dissociation", "impaired_capacity"],
    },
    "severe_intoxication_or_withdrawal": {
        "severity": "high",
        "label": "Intoxication / Withdrawal Concern",
        "reason": "Substance intoxication or withdrawal indicators were present.",
        "required_action": "Medical and safety review before relying on assessment outputs.",
        "triggers": ["intoxicated", "withdrawal_risk"],
    },
    "unstable_medical_state": {
        "severity": "high",
        "label": "Unstable Medical State",
        "reason": "The case suggests concurrent medical instability.",
        "required_action": "Medical review before treatment-support outputs are used.",
        "triggers": ["unstable_medical_state"],
    },
    "abuse_neglect_or_exploitation": {
        "severity": "high",
        "label": "Abuse / Neglect / Exploitation Concern",
        "reason": "Ongoing abuse or safety concerns were present.",
        "required_action": "Follow safeguarding and mandatory-reporting workflow.",
        "triggers": ["ongoing_abuse", "neglect", "exploitation"],
    },
}


CONTRAINDICATION_RULES = {
    "acute_safety": ["suicidal_ideation", "suicide_plan", "recent_attempt", "homicidal_ideation"],
    "pregnancy": ["pregnant", "breastfeeding"],
    "renal_impairment": ["renal_impairment"],
    "hepatic_impairment": ["hepatic_impairment"],
    "seizure_risk": ["seizure_history", "seizure_risk"],
    "bipolar_spectrum_risk": ["mania", "hypomania", "bipolar_history"],
    "psychosis_history": ["psychosis", "psychosis_history"],
    "substance_use_risk": ["substance_use_disorder", "intoxicated", "withdrawal_risk"],
    "sleep_apnea_or_sleep_disorder": ["sleep_apnea", "severe_insomnia", "nightmares"],
    "drug_interactions": ["polypharmacy", "drug_interaction_risk"],
    "trauma_treatment_readiness": ["poor_stabilization", "unsafe_environment", "severe_dissociation"],
    "legal_or_consent_context": ["forensic_context", "consent_concern", "guardian_issue"],
}


REQUIRED_FIELDS = [
    "patient_id",
    "age",
    "symptom_duration_weeks",
    "trauma_exposure_summary",
    "functional_impairment",
]


@dataclass
class CaseEvaluation:
    red_flags: list[dict[str, Any]] = field(default_factory=list)
    contraindications: list[dict[str, Any]] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    assessment_summary: str = ""
    triage_note: str = ""
    clinician_review_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "red_flags": self.red_flags,
            "contraindications": self.contraindications,
            "missing_information": self.missing_information,
            "assessment_summary": self.assessment_summary,
            "triage_note": self.triage_note,
            "clinician_review_required": self.clinician_review_required,
        }


def _truthy(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "present"}
    return bool(value)


def _build_summary(case: dict[str, Any], red_flags: list[dict[str, Any]], missing: list[str]) -> str:
    symptom_count = len(case.get("symptoms", []) or [])
    comorbidity_count = len(case.get("comorbidities", []) or [])
    bits = [
        f"Trauma summary available: {'yes' if case.get('trauma_exposure_summary') else 'no'}",
        f"Symptoms listed: {symptom_count}",
        f"Comorbidities listed: {comorbidity_count}",
        f"Functional impairment documented: {'yes' if case.get('functional_impairment') else 'no'}",
    ]
    if red_flags:
        bits.append(f"Red flags present: {', '.join(flag['code'] for flag in red_flags)}")
    if missing:
        bits.append(f"Missing core fields: {', '.join(missing)}")
    return ". ".join(bits) + "."


def evaluate_case(case: dict[str, Any]) -> CaseEvaluation:
    missing = [field for field in REQUIRED_FIELDS if not case.get(field)]
    red_flags: list[dict[str, Any]] = []
    contraindications: list[dict[str, Any]] = []

    for code, spec in RED_FLAG_RULES.items():
        fired = [trigger for trigger in spec["triggers"] if _truthy(case, trigger)]
        if fired:
            red_flags.append(
                {
                    "code": code,
                    "severity": spec["severity"],
                    "label": spec["label"],
                    "reason": spec["reason"],
                    "required_action": spec["required_action"],
                    "triggered_by": fired,
                }
            )

    for category, triggers in CONTRAINDICATION_RULES.items():
        fired = [trigger for trigger in triggers if _truthy(case, trigger)]
        if fired:
            contraindications.append(
                {
                    "category": category,
                    "triggered_by": fired,
                    "review_only": True,
                }
            )

    triage_note = (
        "High-risk case. Do not rely on treatment-support output without immediate clinician review."
        if red_flags
        else "No critical red flags detected from submitted fields, but clinician review remains required."
    )
    return CaseEvaluation(
        red_flags=red_flags,
        contraindications=contraindications,
        missing_information=missing,
        assessment_summary=_build_summary(case, red_flags, missing),
        triage_note=triage_note,
        clinician_review_required=True,
    )
