# Postgres Runtime Path

## Intent

Postgres in this repo is now a first-class runtime path at the adapter and migration layer for the planned multi-user deployment cutover. SQLite remains the verified default runtime, but the codebase no longer hard-fails the Postgres branch during adapter setup.

The intended path is:

1. `DatabaseSettings.from_target(...)` in `src/ptsd_support/db/adapter.py` selects the engine from environment.
2. `connect(...)` in the same module is the adapter boundary used by schema setup and migrations.
3. `src/ptsd_support/db/schema.py` and `src/ptsd_support/db/migrations.py` call that adapter instead of opening SQLite connections directly.

That means Postgres enablement is expected to happen at the adapter layer first, then flow through migrations, schema setup, and service tests.

## Current Status

Current behavior:

- default runtime: SQLite
- Postgres opt-in marker: `PTSD_SUPPORT_DB_ENGINE=postgres`
- Postgres DSN: `PTSD_SUPPORT_POSTGRES_DSN`
- `connect(...)` opens a psycopg connection when the Postgres engine is selected
- migrations now choose an engine-specific SQL directory
- Postgres-specific migration files exist under `src/ptsd_support/db/migrations/postgres`

Current boundary:

- SQLite remains the fully verified application runtime
- Postgres adapter setup, SQL placeholder translation, and migration selection are implemented
- the broader service layer is written to work against adapter-normalized mapping rows
- a live Postgres database has not yet been exercised end-to-end in this environment

## Local Setup For The Planned Postgres Track

The repo includes the pieces needed to prepare a local Postgres environment:

- optional dependency group in `pyproject.toml`: `.[postgres]`
- local service definition: `docker-compose.postgres.yml`

Example setup:

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
python3 -m pip install -e '.[postgres]'
docker compose -f docker-compose.postgres.yml up -d
```

The compose file starts a local Postgres 16 instance with:

- host: `127.0.0.1`
- port: `5432`
- database: `ptsd_support`
- user: `ptsd`
- password: `ptsd`

An example DSN for the future adapter implementation is:

```text
postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support
```

## Environment Variables

The database adapter currently recognizes these variables:

- `PTSD_SUPPORT_DB_ENGINE`
  - unset or any value other than `postgres`: use SQLite
  - `postgres`: select the planned Postgres runtime branch
- `PTSD_SUPPORT_POSTGRES_DSN`
  - read only when `PTSD_SUPPORT_DB_ENGINE=postgres`
  - stored in `DatabaseSettings.postgres_dsn`
  - used by `connect(...)` to open the psycopg connection
- `PTSD_SUPPORT_DB_PATH`
  - SQLite database path when the engine is SQLite or omitted
  - defaults to `data/processed/ptsd_support.db`

Important precedence note:

- if `PTSD_SUPPORT_DB_ENGINE=postgres`, the adapter selects the Postgres branch even if a SQLite target path is passed explicitly
- if `PTSD_SUPPORT_DB_ENGINE` is unset, the adapter stays on SQLite and resolves the path from the explicit target or `PTSD_SUPPORT_DB_PATH`

## Verification Boundary

The repo currently verifies that:

- SQLite settings resolve correctly from explicit targets and environment
- SQLite connections are created with the expected PRAGMAs and row behavior
- qmark placeholders are translated for the Postgres path
- multi-statement migration SQL can be split for non-SQLite execution
- Postgres configuration validation behaves correctly when DSN or driver support is missing

The repo does not currently verify here:

- a live Postgres connection against an actual running database
- end-to-end API and worker flows on Postgres
- query-plan or performance tuning under multi-user load

Treat Postgres as implemented at the adapter/migration layer and ready for explicit environment validation, but not yet signed off as the default deployment runtime.
