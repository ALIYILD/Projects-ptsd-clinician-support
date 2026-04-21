# Cases

Patient-case persistence is stored in:

- `patient_cases`
- `case_reviews`
- `case_recommendation_history`

## API

- `POST /cases`
- `GET /cases`
- `GET /cases/{case_key}`
- `POST /cases/{case_key}/reviews`
- `GET /cases/{case_key}/reviews`

## Notes

- All case outputs remain clinician-review-only.
- Review history is append-only from the backend perspective.
- Recommendation requests can be attached to a saved case via `case_key`.
