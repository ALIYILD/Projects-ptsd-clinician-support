# Startup

## Local

1. Create `.env` from `.env.example` if you want environment-based startup.
2. Ingest literature and guideline seeds.
3. Create an admin API token.
4. Start the backend.

Example:

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
cp .env.example .env
PYTHONPATH=src python3 scripts/ingest_literature.py --db data/processed/ptsd_support.db --inputs /Users/aliyildirim/ptsd_europepmc_papers.csv /Users/aliyildirim/ptsd_pubmed_only.csv /Users/aliyildirim/ptsd_reviews_or_clinical_trials_only.csv
PYTHONPATH=src python3 scripts/ingest_guidelines.py --db data/processed/ptsd_support.db --seed data/raw/guidelines/ptsd_guidelines.json
PYTHONPATH=src python3 scripts/create_api_key.py --db data/processed/ptsd_support.db --user-key admin-1 --display-name "Admin User" --role admin --org-key clinic-a --org-name "Clinic A" --label local-admin
PYTHONPATH=src python3 scripts/run_server.py
```

Postgres validation example:

```bash
PTSD_SUPPORT_DB_ENGINE=postgres \
PTSD_SUPPORT_POSTGRES_DSN=postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support \
PYTHONPATH=src python3 scripts/validate_postgres.py
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

Authenticated example:

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8080/auth/me
```

## Notes

- The backend uses SQLite by default.
- Auth is enabled by default outside tests and requires an API token for non-health endpoints.
- Use `docs/auth.md` for token bootstrap and `docs/postgres-validation.md` for Postgres checks.
- Persist `data/processed` outside the container if you want durable data.
- For heavier concurrent read/write traffic, move from SQLite to Postgres.
