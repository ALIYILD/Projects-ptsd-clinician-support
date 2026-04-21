# Guideline Ingestion

Guideline support is seeded locally from:

- `data/raw/guidelines/ptsd_guidelines.json`

Current seeds include:

- VA/DoD PTSD guideline 2023
- NICE NG116

## Run

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
PYTHONPATH=src python3 scripts/ingest_guidelines.py --db data/processed/ptsd_support.db
```

## API

- `GET /guidelines`
- `GET /guidelines/recommendations?clinical_domain=psychotherapy`
