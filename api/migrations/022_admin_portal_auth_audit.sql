CREATE TABLE IF NOT EXISTS admin_user (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ NULL,
  CONSTRAINT chk_admin_user_role CHECK (role IN ('admin', 'operator', 'viewer'))
);

CREATE TABLE IF NOT EXISTS admin_session (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_user_id UUID NOT NULL REFERENCES admin_user(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_admin_session_active
  ON admin_session(admin_user_id, expires_at)
  WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS admin_audit_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_user_id UUID NULL REFERENCES admin_user(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  tenant_slug TEXT NULL,
  week_start_date DATE NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_event_created
  ON admin_audit_event(created_at DESC);

ALTER TABLE tenant
  ADD COLUMN IF NOT EXISTS disabled_at TIMESTAMPTZ NULL;

ALTER TABLE match_report
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'open',
  ADD COLUMN IF NOT EXISTS resolution_notes TEXT NULL,
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS resolved_by_admin_id UUID NULL REFERENCES admin_user(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_match_report_tenant_status_created
  ON match_report(tenant_id, status, created_at DESC);
