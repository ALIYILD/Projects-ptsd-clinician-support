# Startup

## Local

1. Create `.env` from `.env.example` if you want environment-based startup.
2. Ingest literature and guideline seeds.
3. Start the backend.

Example:

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
cp .env.example .env
PYTHONPATH=src python3 scripts/ingest_literature.py --db data/processed/ptsd_support.db --inputs /Users/aliyildirim/ptsd_europepmc_papers.csv /Users/aliyildirim/ptsd_pubmed_only.csv /Users/aliyildirim/ptsd_reviews_or_clinical_trials_only.csv
PYTHONPATH=src python3 scripts/ingest_guidelines.py --db data/processed/ptsd_support.db --seed data/raw/guidelines/ptsd_guidelines.json
PYTHONPATH=src python3 scripts/run_server.py
```

## Docker

Build and run:

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
cp .env.example .env
docker compose up --build
```

## Health Check

```bash
curl http://127.0.0.1:8080/health
```

## Notes

- The backend uses SQLite by default.
- Persist `data/processed` outside the container if you want durable data.
- For heavier concurrent read/write traffic, move from SQLite to Postgres.
