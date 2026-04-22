CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY,
    org_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_organization_memberships (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    membership_role TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_org_membership_unique
ON user_organization_memberships(user_id, organization_id);

ALTER TABLE patient_cases ADD COLUMN organization_key TEXT;
CREATE INDEX IF NOT EXISTS idx_patient_cases_org
ON patient_cases(organization_key, updated_at DESC);

ALTER TABLE job_runs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE job_runs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 1;
ALTER TABLE job_runs ADD COLUMN next_attempt_at TEXT;

UPDATE patient_cases
SET organization_key = COALESCE(organization_key, 'default-org')
WHERE organization_key IS NULL OR organization_key = '';

INSERT INTO organizations(org_key, name, is_active)
VALUES ('default-org', 'Default Organization', 1)
ON CONFLICT(org_key) DO NOTHING;
