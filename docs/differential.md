# Differential Helper

`src/ptsd_support/services/differential.py` provides a deterministic, clinician-support differential helper for trauma-related presentations.

## Scope

The helper compares:

- PTSD
- Acute stress disorder
- Complex PTSD
- Major depressive disorder
- Generalized anxiety disorder
- Substance-induced symptoms
- TBI overlap
- Psychosis/mania rule-out

## Output shape

`build_differential_diagnosis(case)` returns a review-only payload with:

- `review_only`
- `diagnostic_support_only`
- `summary`
- `comparisons`
- `missing_data`
- `escalation_notes`

Each comparison entry contains:

- `condition`
- `status`
- `supporting_features`
- `contradicting_features`
- `missing_data`

Status values are:

- `higher_priority_review`
- `consider`
- `less_likely`
- `insufficient_data`

## Decision rules

The helper is intentionally conservative:

- PTSD is supported by trauma exposure, intrusion, avoidance, arousal/reactivity, impairment, and duration of at least one month.
- Acute stress disorder is supported when post-traumatic symptoms fall in the 3-day to 1-month window.
- Complex PTSD requires PTSD-like symptoms plus prolonged/repeated trauma and disturbances in self-organization.
- MDD and GAD are surfaced when mood or generalized-anxiety features are present without assuming they fully explain trauma-linked symptoms.
- Substance-induced symptoms are elevated when symptoms are temporally linked to intoxication or withdrawal.
- TBI overlap is elevated when head injury history and post-concussive cognitive/somatic symptoms are present.
- Psychosis/mania rule-out is elevated whenever psychosis-spectrum or mania-spectrum features are documented.

## Safety posture

The helper does not diagnose, prescribe, or clear treatment. It always returns review-only output and emits escalation notes for:

- suicide or violence risk
- psychosis
- mania/hypomania
- intoxication or withdrawal
- head injury or neurologic overlap

## Example

```python
from ptsd_support.services.differential import build_differential_diagnosis

result = build_differential_diagnosis(
    {
        "trauma_exposure_summary": "Motor vehicle collision eight weeks ago.",
        "symptom_duration_weeks": 8,
        "functional_impairment": "Avoiding driving and missing work.",
        "symptoms": ["nightmares", "flashbacks", "avoidance", "hypervigilance"],
    }
)
```
