# Safety

This repository is intended for clinician-support workflows only.

## Required Principles

- Always show source citations.
- Always show uncertainty and missing information.
- Never present model output as a final diagnosis.
- Never present medication or neuromodulation output as an order.
- Escalate hard-stop risk states to immediate clinician review.
- Preserve an audit trail for generated drafts, clinician edits, and sign-off events.

## Initial Red Flags

- suicidal thoughts or behavior
- homicidal thoughts or behavior
- psychosis
- mania
- intoxication or withdrawal
- severe functional collapse
- severe dissociation or impaired capacity
- abuse, neglect, or exploitation concerns

## Workflow Controls

- Use draft-only language for model outputs.
- Block finalization when critical data is missing.
- Block patient-facing export when unresolved red flags exist.
- Require explicit clinician acknowledgement for red-flag dismissal.
- Require explicit clinician sign-off for summaries, risk flags, care plans, and patient-facing text.

## Output Requirement

Every recommendation-oriented response should include:

- evidence summary
- citations
- reasons for and against
- contraindications and cautions
- missing information
- clinician review note

## Prohibited Autonomous Behaviors

- final diagnosis statements
- medication start, stop, dose, taper, or cross-taper instructions
- autonomous neuromodulation protocol generation
- automatic patient messaging
- automatic emergency escalation outside clinician workflow
- silent closing of alerts

## Backend Enforcement

- Case evaluation should emit explicit red flags and contraindication categories.
- Recommendation endpoints should return evidence support only.
- Audit logging should capture search, assessment, and support-plan requests.
- Every backend output should remain clinician-review-only.
