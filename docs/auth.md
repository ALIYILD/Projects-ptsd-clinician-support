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

API token endpoints:

- `GET /auth/tokens`
- `POST /auth/tokens`
- `POST /auth/tokens/revoke`
- `POST /auth/tokens/rotate`

For non-admin users, these endpoints are automatically limited to the current actor's own tokens.

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

List tokens for the current actor:

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8080/auth/tokens
```

Issue a new token for the current actor:

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"label":"secondary"}' \
  http://127.0.0.1:8080/auth/tokens
```

Issue a token with expiry:

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"label":"temporary","ttl_days":7}' \
  http://127.0.0.1:8080/auth/tokens
```

Revoke a token by prefix:

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"token_prefix":"ptsd_abcd"}' \
  http://127.0.0.1:8080/auth/tokens/revoke
```

Rotate a token by prefix:

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"token_prefix":"ptsd_abcd","ttl_days":30}' \
  http://127.0.0.1:8080/auth/tokens/rotate
```

## Notes

- `GET /health` remains unauthenticated.
- `PTSD_SUPPORT_REQUIRE_AUTH=true` is the recommended default.
- Tokens are stored as hashes in the database. The plaintext token is only available at creation time.
- `admin` bypasses organization filters. `viewer` and `clinician` are scoped to their organization memberships.
- Care plans and note drafts now inherit the same case/org access boundaries as case reads and writes.
- Tokens can now expire, be revoked, and be rotated without reusing the original secret.
- Admin-only audit log read endpoints are available at `GET /admin/audit` and `GET /admin/requests`.
