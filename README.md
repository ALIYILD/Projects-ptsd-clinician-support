# PTSD Clinician Support

Clinician-facing PTSD evidence support system.

This repository is scoped for:

- structured evidence ingestion
- guideline-backed retrieval
- explainable clinical decision support
- assessment support
- safety guardrails

This repository is not scoped for:

- autonomous diagnosis
- autonomous prescribing
- autonomous neuromodulation protocol generation
- direct-to-patient treatment recommendations

## Status

Initial scaffold with:

- SQLite schema
- CSV ingestion pipeline for existing PTSD literature exports
- safety rules config
- MVP project layout
- backend JSON API for literature, assessment, and support-plan workflows
- guideline ingestion
- patient-case persistence and review history
- deterministic treatment-support rules
- explicit SQL migrations
- file-backed background ingestion worker
- differential support
- care-plan and home-task generation
- clinician note drafting

## Project Layout

- `src/ptsd_support/db`: database schema and SQLite helpers
- `src/ptsd_support/ingest`: literature ingestion pipeline
- `src/ptsd_support/api`: API placeholders for later clinician UI/backend work
- `src/ptsd_support/services`: retrieval and support services
- `config`: safety and app configuration
- `docs`: product, data, and safety documentation
- `data/raw`: raw input files
- `data/processed`: generated database and outputs

## Quick Start

1. Create a virtual environment and install the package.
2. Copy or reference PTSD CSV exports into `data/raw` or pass explicit paths.
3. Run the ingestion script.

Example:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/ingest_literature.py --db data/processed/ptsd_support.db --inputs /Users/aliyildirim/ptsd_europepmc_papers.csv /Users/aliyildirim/ptsd_pubmed_only.csv /Users/aliyildirim/ptsd_reviews_or_clinical_trials_only.csv
PYTHONPATH=src python3 scripts/migrate_db.py --db data/processed/ptsd_support.db
PYTHONPATH=src python3 scripts/query_literature.py --db data/processed/ptsd_support.db --reviews-or-trials --limit 5
PYTHONPATH=src python3 scripts/ingest_guidelines.py --db data/processed/ptsd_support.db
PYTHONPATH=src python3 scripts/run_server.py --db data/processed/ptsd_support.db --port 8080
```

Environment-driven startup:

```bash
cp .env.example .env
PYTHONPATH=src python3 scripts/bootstrap_backend.py
```

## Backend Endpoints

- `GET /health`
- `GET /literature/search`
- `GET /literature/summary`
- `GET /guidelines`
- `GET /guidelines/recommendations`
- `POST /cases`
- `GET /cases`
- `GET /cases/{case_key}`
- `POST /cases/{case_key}/reviews`
- `GET /cases/{case_key}/reviews`
- `POST /decision-support/differential`
- `POST /assessment/evaluate`
- `POST /recommendations/support-plan`
- `POST /care-plans/generate`
- `GET /cases/{case_key}/care-plans`
- `POST /cases/{case_key}/care-plans`
- `POST /notes/draft`
- `GET /cases/{case_key}/notes`
- `POST /cases/{case_key}/notes`

## Deployment Prep

- `.env.example` for runtime configuration
- `Dockerfile` for container builds
- `docker-compose.yml` for local container startup
- [startup.md](docs/startup.md) for local and Docker startup
- [deployment.md](docs/deployment.md) for WAL mode, request logging, and Postgres track notes
- [worker.md](docs/worker.md) for background ingestion

## MVP Roadmap

1. Ingest literature and normalize evidence metadata.
2. Add guideline ingestion for VA/DoD and NICE.
3. Add retrieval layer with citations.
4. Add assessment workflows and safety guardrails.
5. Add clinician-facing UI/API.
