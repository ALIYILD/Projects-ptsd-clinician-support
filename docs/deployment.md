# Deployment

## Verified Runtime

The currently verified runtime is:

- SQLite
- WAL mode enabled
- JSONL audit log
- JSONL request log
- local or Docker startup

## SQLite Hardening

The SQLite connection is configured with:

- `journal_mode=WAL`
- `synchronous=NORMAL`
- `busy_timeout=30000`

This improves concurrent UI reads during background ingestion and write-heavy workflows.

## Structured Logging

Operational request logs are written to:

- `PTSD_SUPPORT_REQUEST_LOG`

Clinical audit events are written to:

- `PTSD_SUPPORT_AUDIT_LOG`

Every API response now includes:

- `request_id`

Internal server errors also include:

- `error_id`

## Postgres Track

This repo now includes:

- optional Python dependency group: `.[postgres]`
- `docker-compose.postgres.yml` for a local Postgres service

Postgres is prepared as the next storage target for multi-user deployment, but the backend in this repo is still verified only on the SQLite path right now. The current SQL and service layer remain SQLite-first and should be migrated carefully before a production Postgres cutover.

## Recommended Next Migration Steps

1. Introduce a database adapter layer for SQLite and Postgres parameter styles.
2. Port schema creation to explicit SQL migrations for both engines.
3. Run concurrency and transaction tests against Postgres.
4. Move long-running ingestion to a worker process.
