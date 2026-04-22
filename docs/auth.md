# Authentication

## Model

The backend now supports database-backed API key authentication with simple role enforcement.

Supported roles:

- `viewer`
- `clinician`
- `admin`

Role behavior:

- `viewer`: read-only literature, guideline, and `/auth/me` access
- `clinician`: clinician workflow endpoints and read access
- `admin`: full access, including background job management

Users are also organization-scoped unless they are `admin`. Case APIs now default new cases into the actor's default organization, and non-admin actors only see cases inside their memberships.

## Headers

Use either:

- `Authorization: Bearer <token>`
- `X-API-Key: <token>`

## Bootstrap

Create a user and issue a token:

```bash
cd /Users/aliyildirim/Projects/ptsd-clinician-support
PYTHONPATH=src python3 scripts/create_api_key.py \
  --db data/processed/ptsd_support.db \
  --user-key admin-1 \
  --display-name "Admin User" \
  --role admin \
  --label local-admin
```

To create or use a named organization and make it the default scope:

```bash
PYTHONPATH=src python3 scripts/create_api_key.py \
  --db data/processed/ptsd_support.db \
  --user-key clinician-1 \
  --display-name "Clinician One" \
  --role clinician \
  --org-key clinic-a \
  --org-name "Clinic A" \
  --label clinic-a-primary
```

The command prints the plaintext token once. Store it securely.

## Auth Check

Inspect the current actor:

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8080/auth/me
```

## Notes

- `GET /health` remains unauthenticated.
- `PTSD_SUPPORT_REQUIRE_AUTH=true` is the recommended default.
- Tokens are stored as hashes in the database. The plaintext token is only available at creation time.
- `admin` bypasses organization filters. `viewer` and `clinician` are scoped to their organization memberships.
