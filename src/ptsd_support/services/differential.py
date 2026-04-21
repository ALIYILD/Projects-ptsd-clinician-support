from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


COMPARISON_ORDER = [
    "ptsd",
    "acute_stress_disorder",
    "complex_ptsd",
    "major_depressive_disorder",
    "generalized_anxiety_disorder",
    "substance_induced_symptoms",
    "tbi_overlap",
    "psychosis_or_mania_rule_out",
]


STATUS_LABELS = {
    "high": "higher_priority_review",
    "moderate": "consider",
    "low": "less_likely",
    "insufficient": "insufficient_data",
}


@dataclass
class ComparisonResult:
    condition: str
    status: str
    supporting_features: list[str] = field(default_factory=list)
    contradicting_features: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "status": self.status,
            "supporting_features": self.supporting_features,
            "contradicting_features": self.contradicting_features,
            "missing_data": self.missing_data,
        }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "present", "positive"}
    return bool(value)


def _coerce_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            items.extend(_flatten_strings(item))
        return items
    if isinstance(value, dict):
        return [str(item) for item in value.keys()]
    return [str(value)]


def _collect_text(case: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "symptoms",
        "presenting_problems",
        "trauma_exposure_summary",
        "history",
        "notes",
        "substance_use_summary",
        "injury_summary",
        "mood_summary",
        "anxiety_summary",
    ):
        parts.extend(_flatten_strings(case.get(key)))
    flags = case.get("flags")
    if isinstance(flags, dict):
        for name, value in flags.items():
            if _truthy(value):
                parts.append(name)
    return " ".join(parts).lower()


def _has_any(case: dict[str, Any], text_blob: str, *, keys: list[str], terms: list[str]) -> bool:
    for key in keys:
        if _truthy(case.get(key)):
            return True
        flags = case.get("flags")
        if isinstance(flags, dict) and _truthy(flags.get(key)):
            return True
    return any(term in text_blob for term in terms)


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _duration_days(case: dict[str, Any]) -> float | None:
    direct_days = _coerce_number(case.get("symptom_duration_days"))
    if direct_days is not None:
        return direct_days
    weeks = _coerce_number(case.get("symptom_duration_weeks"))
    if weeks is not None:
        return weeks * 7.0
    months = _coerce_number(case.get("symptom_duration_months"))
    if months is not None:
        return months * 30.0
    return None


def _determine_status(score: int, supporting_count: int, missing_count: int) -> str:
    if supporting_count == 0 and missing_count >= 2:
        return STATUS_LABELS["insufficient"]
    if score >= 4:
        return STATUS_LABELS["high"]
    if score >= 2:
        return STATUS_LABELS["moderate"]
    if missing_count >= 3 and supporting_count == 0:
        return STATUS_LABELS["insufficient"]
    return STATUS_LABELS["low"]


def _build_ptsd(case: dict[str, Any], text_blob: str, duration_days: float | None) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    trauma_exposure = bool(case.get("trauma_exposure_summary")) or _truthy(case.get("trauma_exposure"))
    intrusion = _has_any(
        case,
        text_blob,
        keys=["intrusions", "flashbacks", "nightmares", "physiologic_reactivity"],
        terms=["flashback", "nightmare", "intrusive", "re-experien", "physiologic reactivity"],
    )
    avoidance = _has_any(
        case,
        text_blob,
        keys=["avoidance", "avoidance_of_memories", "avoidance_of_reminders"],
        terms=["avoidance", "avoids reminders", "avoids memories"],
    )
    arousal = _has_any(
        case,
        text_blob,
        keys=["hypervigilance", "startle", "irritability", "sleep_disturbance"],
        terms=["hypervigil", "startle", "irritab", "sleep disturbance"],
    )
    impairment = bool(case.get("functional_impairment")) or _truthy(case.get("functional_decline"))

    if trauma_exposure:
        _append_unique(supporting, "Trauma exposure is documented.")
        score += 1
    else:
        _append_unique(missing, "Clarify whether the patient had a qualifying trauma exposure.")

    if intrusion:
        _append_unique(supporting, "Intrusion symptoms are present.")
        score += 1
    else:
        _append_unique(missing, "Assess for intrusion symptoms such as nightmares, flashbacks, or intrusive memories.")

    if avoidance:
        _append_unique(supporting, "Trauma-related avoidance is described.")
        score += 1
    else:
        _append_unique(missing, "Assess for trauma-related avoidance.")

    if arousal:
        _append_unique(supporting, "Arousal/reactivity symptoms are present.")
        score += 1

    if impairment:
        _append_unique(supporting, "Functional impairment is documented.")
        score += 1
    else:
        _append_unique(missing, "Document whether symptoms cause functional impairment.")

    if duration_days is None:
        _append_unique(missing, "Document symptom duration relative to the trauma.")
    elif duration_days >= 30:
        _append_unique(supporting, "Symptom duration is at least one month, which fits PTSD timing better than acute stress disorder.")
        score += 1
    else:
        _append_unique(contradicting, "Symptom duration is under one month, which argues against PTSD timing.")
        score -= 1

    if _has_any(
        case,
        text_blob,
        keys=["psychosis", "hallucinations", "delusions", "mania", "hypomania"],
        terms=["hallucination", "delusion", "manic", "grandios", "decreased need for sleep"],
    ):
        _append_unique(contradicting, "Psychosis or mania features require alternative explanation before relying on a PTSD formulation.")

    return ComparisonResult(
        condition="PTSD",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_asd(case: dict[str, Any], text_blob: str, duration_days: float | None) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    trauma_exposure = bool(case.get("trauma_exposure_summary")) or _truthy(case.get("trauma_exposure"))
    acute_window_known = duration_days is not None
    intrusion_or_dissociation = _has_any(
        case,
        text_blob,
        keys=["intrusions", "flashbacks", "nightmares", "dissociation", "depersonalization", "derealization"],
        terms=["flashback", "nightmare", "intrusive", "dissoci", "depersonalization", "derealization"],
    )

    if trauma_exposure:
        _append_unique(supporting, "Trauma exposure is documented.")
        score += 1
    else:
        _append_unique(missing, "Clarify whether the presentation followed a qualifying trauma.")

    if intrusion_or_dissociation:
        _append_unique(supporting, "Early post-traumatic symptoms or dissociation are present.")
        score += 1
    else:
        _append_unique(missing, "Assess for intrusion or dissociative symptoms in the immediate post-trauma period.")

    if acute_window_known:
        if 3 <= duration_days <= 30:
            _append_unique(supporting, "Duration falls in the 3-day to 1-month window that fits acute stress disorder.")
            score += 2
        elif duration_days < 3:
            _append_unique(contradicting, "Symptoms are too early to confirm acute stress disorder timing.")
        else:
            _append_unique(contradicting, "Symptom duration is beyond one month, which argues against acute stress disorder.")
            score -= 1
    else:
        _append_unique(missing, "Document exact symptom duration in days or weeks.")

    if bool(case.get("functional_impairment")) or _truthy(case.get("functional_decline")):
        _append_unique(supporting, "Functional impairment is documented.")
        score += 1
    else:
        _append_unique(missing, "Document whether symptoms are impairing.")

    return ComparisonResult(
        condition="Acute stress disorder",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_complex_ptsd(case: dict[str, Any], text_blob: str, duration_days: float | None) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    repeated_trauma = _has_any(
        case,
        text_blob,
        keys=["repeated_trauma", "prolonged_trauma", "captivity", "childhood_trauma"],
        terms=["childhood abuse", "repeated trauma", "prolonged trauma", "captivity", "chronic abuse"],
    )
    ptsd_core = _has_any(
        case,
        text_blob,
        keys=["intrusions", "avoidance", "hypervigilance", "flashbacks", "nightmares"],
        terms=["flashback", "nightmare", "intrusive", "avoidance", "hypervigil"],
    )
    self_organization_disturbance = _has_any(
        case,
        text_blob,
        keys=["affect_dysregulation", "negative_self_concept", "relational_disturbance"],
        terms=["emotion dysreg", "affect dysreg", "worthless", "shame", "relationship disturbance", "interpersonal difficulty"],
    )

    if repeated_trauma:
        _append_unique(supporting, "Repeated or prolonged trauma exposure is described.")
        score += 2
    else:
        _append_unique(missing, "Clarify whether trauma was prolonged, repeated, or developmental.")

    if ptsd_core:
        _append_unique(supporting, "Core post-traumatic symptoms are present.")
        score += 1
    else:
        _append_unique(missing, "Assess for core PTSD symptoms before considering complex PTSD.")

    if self_organization_disturbance:
        _append_unique(supporting, "Disturbances in self-organization are described.")
        score += 2
    else:
        _append_unique(missing, "Assess for affect dysregulation, negative self-concept, and relational disturbance.")

    if duration_days is not None and duration_days < 30:
        _append_unique(contradicting, "Very short symptom duration makes a chronic complex PTSD formulation less convincing.")

    return ComparisonResult(
        condition="Complex PTSD",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_mdd(case: dict[str, Any], text_blob: str) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    depression_core = _has_any(
        case,
        text_blob,
        keys=["depressed_mood", "anhedonia"],
        terms=["depressed mood", "anhedonia", "loss of interest", "hopeless", "worthless"],
    )
    neurovegetative = _has_any(
        case,
        text_blob,
        keys=["appetite_change", "sleep_disturbance", "psychomotor_change", "fatigue", "guilt", "concentration_difficulty"],
        terms=["appetite", "insomnia", "hypersomnia", "fatigue", "guilt", "poor concentration", "psychomotor"],
    )
    trauma_specific = _has_any(
        case,
        text_blob,
        keys=["intrusions", "flashbacks", "nightmares", "avoidance"],
        terms=["flashback", "nightmare", "intrusive", "avoidance"],
    )

    if depression_core:
        _append_unique(supporting, "Depressed mood or anhedonia is present.")
        score += 2
    else:
        _append_unique(missing, "Assess for depressed mood and loss of interest.")

    if neurovegetative:
        _append_unique(supporting, "Additional depressive symptoms are present.")
        score += 1
    else:
        _append_unique(missing, "Assess for sleep, appetite, energy, guilt, and concentration changes.")

    if trauma_specific:
        _append_unique(contradicting, "Marked trauma-specific re-experiencing or avoidance suggests the presentation may not be explained by MDD alone.")

    return ComparisonResult(
        condition="Major depressive disorder",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_gad(case: dict[str, Any], text_blob: str) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    generalized_worry = _has_any(
        case,
        text_blob,
        keys=["excessive_worry", "difficulty_controlling_worry"],
        terms=["excessive worry", "uncontrollable worry", "worries about multiple domains", "generalized anxiety"],
    )
    gad_associated = _has_any(
        case,
        text_blob,
        keys=["restlessness", "fatigue", "concentration_difficulty", "irritability", "muscle_tension", "sleep_disturbance"],
        terms=["restless", "fatigue", "irritab", "muscle tension", "sleep disturbance"],
    )
    trauma_specific = _has_any(
        case,
        text_blob,
        keys=["intrusions", "flashbacks", "nightmares", "avoidance"],
        terms=["flashback", "nightmare", "intrusive", "avoidance"],
    )

    if generalized_worry:
        _append_unique(supporting, "Persistent, difficult-to-control worry is described.")
        score += 2
    else:
        _append_unique(missing, "Assess whether worry is excessive, generalized, and hard to control.")

    if gad_associated:
        _append_unique(supporting, "Associated anxiety symptoms are present.")
        score += 1
    else:
        _append_unique(missing, "Assess for restlessness, tension, irritability, fatigue, and sleep disturbance.")

    if trauma_specific:
        _append_unique(contradicting, "Prominent trauma-cued re-experiencing points away from GAD as the sole explanation.")

    return ComparisonResult(
        condition="Generalized anxiety disorder",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_substance(case: dict[str, Any], text_blob: str) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    recent_use = _has_any(
        case,
        text_blob,
        keys=["recent_substance_use", "intoxicated", "withdrawal_risk", "substance_use_disorder"],
        terms=["intox", "withdraw", "alcohol use", "cannabis use", "stimulant use", "substance use"],
    )
    temporal_link = _has_any(
        case,
        text_blob,
        keys=["symptoms_after_substance_use", "symptoms_during_withdrawal"],
        terms=["after using", "during withdrawal", "after intoxication", "substance-induced"],
    )

    if recent_use:
        _append_unique(supporting, "Recent substance use, intoxication, or withdrawal risk is present.")
        score += 1
    else:
        _append_unique(missing, "Document recent substance use, intoxication, or withdrawal history.")

    if temporal_link:
        _append_unique(supporting, "Symptoms appear temporally linked to substance use or withdrawal.")
        score += 2
    else:
        _append_unique(missing, "Clarify whether symptoms began or worsened during intoxication or withdrawal.")

    if bool(case.get("trauma_exposure_summary")) and _has_any(
        case,
        text_blob,
        keys=["intrusions", "flashbacks", "avoidance", "nightmares"],
        terms=["flashback", "nightmare", "intrusive", "avoidance"],
    ):
        _append_unique(contradicting, "Clear trauma-linked symptoms suggest substance effects may not fully explain the presentation.")

    return ComparisonResult(
        condition="Substance-induced symptoms",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_tbi(case: dict[str, Any], text_blob: str) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    head_injury = _has_any(
        case,
        text_blob,
        keys=["head_injury", "tbi_history", "loss_of_consciousness", "post_concussive_symptoms"],
        terms=["tbi", "concussion", "head injury", "loss of consciousness", "post-concussive"],
    )
    cognitive_somatic = _has_any(
        case,
        text_blob,
        keys=["headache", "dizziness", "memory_problem", "concentration_difficulty", "light_sensitivity"],
        terms=["headache", "dizziness", "memory", "concentration", "light sensitivity"],
    )

    if head_injury:
        _append_unique(supporting, "Head injury or TBI history is documented.")
        score += 2
    else:
        _append_unique(missing, "Clarify whether there was concussion, TBI, or loss of consciousness.")

    if cognitive_somatic:
        _append_unique(supporting, "Cognitive or somatic symptoms overlap with post-concussive/TBI presentations.")
        score += 1
    else:
        _append_unique(missing, "Assess for headaches, dizziness, cognitive slowing, and sensory sensitivity.")

    if _has_any(
        case,
        text_blob,
        keys=["intrusions", "nightmares", "avoidance", "flashbacks"],
        terms=["flashback", "nightmare", "intrusive", "avoidance"],
    ):
        _append_unique(contradicting, "Trauma-specific re-experiencing suggests TBI alone is unlikely to explain all symptoms.")

    return ComparisonResult(
        condition="TBI overlap",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _build_psychosis_mania(case: dict[str, Any], text_blob: str) -> ComparisonResult:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    score = 0

    psychosis = _has_any(
        case,
        text_blob,
        keys=["psychosis", "hallucinations", "delusions", "disorganized_thought"],
        terms=["hallucination", "delusion", "disorganized", "thought disorder"],
    )
    mania = _has_any(
        case,
        text_blob,
        keys=["mania", "hypomania", "grandiosity", "decreased_need_for_sleep", "pressured_speech"],
        terms=["manic", "grandios", "decreased need for sleep", "pressured speech", "euphoric"],
    )

    if psychosis:
        _append_unique(supporting, "Psychotic symptoms are described and require primary psychotic, mood, substance, or medical rule-out.")
        score += 2
    else:
        _append_unique(missing, "Assess for hallucinations, delusions, and disorganization.")

    if mania:
        _append_unique(supporting, "Mania/hypomania features are present and require bipolar-spectrum rule-out.")
        score += 2
    else:
        _append_unique(missing, "Assess for elevated mood, decreased need for sleep, grandiosity, and pressured speech.")

    if not psychosis and not mania:
        _append_unique(contradicting, "No psychosis or mania features are currently documented.")

    return ComparisonResult(
        condition="Psychosis/mania rule-out",
        status=_determine_status(score, len(supporting), len(missing)),
        supporting_features=supporting,
        contradicting_features=contradicting,
        missing_data=missing,
    )


def _escalation_notes(case: dict[str, Any], text_blob: str) -> list[str]:
    notes: list[str] = []
    checks = [
        (
            _has_any(
                case,
                text_blob,
                keys=["suicidal_ideation", "suicide_plan", "recent_attempt"],
                terms=["suicidal", "suicide plan", "recent attempt"],
            ),
            "Immediate safety review is indicated because suicide risk features are present.",
        ),
        (
            _has_any(
                case,
                text_blob,
                keys=["homicidal_ideation", "violence_risk"],
                terms=["homicidal", "violent ideation"],
            ),
            "Immediate safety review is indicated because violence risk features are present.",
        ),
        (
            _has_any(
                case,
                text_blob,
                keys=["psychosis", "hallucinations", "delusions", "disorganized_thought"],
                terms=["hallucination", "delusion", "disorganized"],
            ),
            "Urgent psychiatric or medical assessment is indicated because psychosis-spectrum symptoms are present.",
        ),
        (
            _has_any(
                case,
                text_blob,
                keys=["mania", "hypomania", "grandiosity", "decreased_need_for_sleep"],
                terms=["manic", "grandios", "decreased need for sleep"],
            ),
            "Urgent clinician review is indicated because mania-spectrum symptoms are present.",
        ),
        (
            _has_any(
                case,
                text_blob,
                keys=["intoxicated", "withdrawal_risk"],
                terms=["intox", "withdraw"],
            ),
            "Medical review is indicated before relying on the differential because intoxication or withdrawal may be contributing.",
        ),
        (
            _has_any(
                case,
                text_blob,
                keys=["head_injury", "loss_of_consciousness", "neurologic_red_flags"],
                terms=["loss of consciousness", "neurologic deficit", "seizure after head injury"],
            ),
            "Neurologic or medical assessment is indicated because TBI or head-injury overlap may change interpretation.",
        ),
    ]
    for fired, note in checks:
        if fired:
            _append_unique(notes, note)
    if not notes:
        notes.append("No automatic escalation triggers were detected from submitted fields, but clinician review is still required.")
    return notes


def build_differential_diagnosis(case: dict[str, Any]) -> dict[str, Any]:
    text_blob = _collect_text(case)
    duration_days = _duration_days(case)

    comparisons = {
        "ptsd": _build_ptsd(case, text_blob, duration_days),
        "acute_stress_disorder": _build_asd(case, text_blob, duration_days),
        "complex_ptsd": _build_complex_ptsd(case, text_blob, duration_days),
        "major_depressive_disorder": _build_mdd(case, text_blob),
        "generalized_anxiety_disorder": _build_gad(case, text_blob),
        "substance_induced_symptoms": _build_substance(case, text_blob),
        "tbi_overlap": _build_tbi(case, text_blob),
        "psychosis_or_mania_rule_out": _build_psychosis_mania(case, text_blob),
    }

    overall_missing: list[str] = []
    for key in COMPARISON_ORDER:
        for item in comparisons[key].missing_data:
            _append_unique(overall_missing, item)

    return {
        "review_only": True,
        "diagnostic_support_only": True,
        "summary": "Deterministic differential support for trauma-related presentations. This output does not establish a diagnosis and requires clinician review.",
        "comparisons": [comparisons[key].to_dict() for key in COMPARISON_ORDER],
        "missing_data": overall_missing,
        "escalation_notes": _escalation_notes(case, text_blob),
    }
