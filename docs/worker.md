# Background Worker

Long-running ingestion should not block the API process.

This repo now includes a file-backed job queue under:

- `data/processed/jobs/pending`
- `data/processed/jobs/running`
- `data/processed/jobs/done`
- `data/processed/jobs/failed`

## Enqueue Literature Ingestion

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
PYTHONPATH=src python3 scripts/enqueue_ingestion_job.py \
  --job-type ingest_literature \
  --db data/processed/ptsd_support.db \
  --inputs /Users/aliyildirim/ptsd_europepmc_papers.csv /Users/aliyildirim/ptsd_pubmed_only.csv /Users/aliyildirim/ptsd_reviews_or_clinical_trials_only.csv
```

## Enqueue Guideline Ingestion

```bash
PYTHONPATH=src python3 scripts/enqueue_ingestion_job.py \
  --job-type ingest_guidelines \
  --db data/processed/ptsd_support.db \
  --seed data/raw/guidelines/ptsd_guidelines.json
```

## Run Worker

```bash
PYTHONPATH=src python3 scripts/run_worker.py
```

## Notes

- This is a pragmatic local worker implementation.
- It is intended to decouple ingestion from the API now.
- Job state is also mirrored into the `job_runs` table for API visibility.
- Jobs can retry up to `max_attempts` before settling as failed.
- Admin APIs now expose `POST /jobs`, `GET /jobs`, `GET /jobs/{job_id}`, and `POST /jobs/{job_id}/retry`.
- The next production step would be a real queue and worker runtime.
