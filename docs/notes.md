# Notes

The backend can draft structured clinician notes for:

- assessment summary
- risk summary
- support-plan summary
- care-plan summary

Endpoints:

- `POST /notes/draft`
- `GET /cases/{case_key}/notes`
- `POST /cases/{case_key}/notes`

All note outputs remain draft artifacts that require clinician review.
