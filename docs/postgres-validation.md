# Postgres Validation

`scripts/validate_postgres.py` performs a practical validation pass against the current Postgres adapter configuration.

## What It Validates

- Resolved database configuration uses `postgres` rather than `sqlite`
- A Postgres DSN is available from `PTSD_SUPPORT_POSTGRES_DSN` or `--dsn`
- The adapter can establish a Postgres connection
- Database migrations run successfully through the existing migration entrypoint
- A minimal health query succeeds with `SELECT 1`
- The server responds to `SELECT version()`

## Usage

From the repository root:

```bash
PYTHONPATH=src python scripts/validate_postgres.py
```

To validate an explicit DSN without relying on environment variables:

```bash
PYTHONPATH=src python scripts/validate_postgres.py --dsn postgresql://ptsd:ptsd@127.0.0.1:5432/ptsd_support
```

## Expected Output

The script prints a step-by-step report. Successful runs emit `OK` for configuration, connection, migrations, health, and server version checks and exit with status `0`. Failures print the failing step and return status `1`.

## Scope

The script is intended as an operator-facing validation pass for environments where Postgres and `psycopg` may or may not be installed yet. The unit tests for this script are mock-only and do not require a live Postgres server.
