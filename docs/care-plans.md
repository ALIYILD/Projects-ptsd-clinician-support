# Care Plans

The backend can generate clinician-review-only care plans and between-session task drafts.

Endpoints:

- `POST /care-plans/generate`
- `GET /cases/{case_key}/care-plans`
- `POST /cases/{case_key}/care-plans`

Notes:

- Output is blocked when major safety red flags are active.
- Home tasks are drafts for clinician sign-off only.
- Persisted plans are stored in `care_plans`.
