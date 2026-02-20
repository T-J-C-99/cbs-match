CREATE TABLE IF NOT EXISTS tenant (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  email_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
  timezone TEXT NOT NULL DEFAULT 'America/New_York',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO tenant (slug, name, email_domains, timezone)
VALUES ('cbs', 'Columbia Business School', '["gsb.columbia.edu"]'::jsonb, 'America/New_York')
ON CONFLICT (slug) DO NOTHING;

ALTER TABLE user_account ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE survey_session ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE user_traits ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE weekly_match_assignment ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE match_feedback ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE user_block ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE match_report ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);

UPDATE user_account ua
SET tenant_id = t.id
FROM tenant t
WHERE t.slug = 'cbs'
  AND ua.tenant_id IS NULL;

UPDATE user_profile up
SET tenant_id = COALESCE(up.tenant_id, ua.tenant_id)
FROM user_account ua
WHERE up.user_id = ua.id;

UPDATE survey_session ss
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE ss.tenant_id IS NULL
  AND ua.id = CAST(ss.user_id AS uuid);

UPDATE user_traits ut
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE ut.tenant_id IS NULL
  AND ua.id = CAST(ut.user_id AS uuid);

UPDATE weekly_match_assignment wma
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE wma.tenant_id IS NULL
  AND ua.id = wma.user_id;

UPDATE match_feedback mf
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE mf.tenant_id IS NULL
  AND ua.id = mf.user_id;

UPDATE user_block ub
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE ub.tenant_id IS NULL
  AND ua.id = ub.user_id;

UPDATE match_report mr
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE mr.tenant_id IS NULL
  AND ua.id = mr.user_id;

CREATE INDEX IF NOT EXISTS idx_user_account_tenant_id ON user_account(tenant_id);
CREATE INDEX IF NOT EXISTS idx_weekly_match_assignment_tenant_week ON weekly_match_assignment(tenant_id, week_start_date);
CREATE INDEX IF NOT EXISTS idx_user_traits_tenant_user ON user_traits(tenant_id, user_id);

CREATE TABLE IF NOT EXISTS user_vibe_card (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  tenant_id UUID REFERENCES tenant(id),
  survey_slug TEXT NOT NULL,
  survey_version INT NOT NULL,
  vibe_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, survey_slug, survey_version)
);

CREATE INDEX IF NOT EXISTS idx_user_vibe_card_tenant_created ON user_vibe_card(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS product_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NULL REFERENCES user_account(id) ON DELETE SET NULL,
  tenant_id UUID NULL REFERENCES tenant(id),
  session_id UUID NULL REFERENCES survey_session(id) ON DELETE SET NULL,
  event_name TEXT NOT NULL,
  properties JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_event_name_created ON product_event(event_name, created_at);
CREATE INDEX IF NOT EXISTS idx_product_event_user_created ON product_event(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_product_event_tenant_created ON product_event(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS notification_preference (
  user_id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE,
  tenant_id UUID REFERENCES tenant(id),
  email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  push_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  quiet_hours_start_local TIME NULL,
  quiet_hours_end_local TIME NULL,
  timezone TEXT NOT NULL DEFAULT 'America/New_York',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_outbox (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  tenant_id UUID REFERENCES tenant(id),
  channel TEXT NOT NULL,
  template_key TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  idempotency_key TEXT UNIQUE NOT NULL,
  scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMPTZ NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  last_error TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_status_sched ON notification_outbox(status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_notification_outbox_tenant_created ON notification_outbox(tenant_id, created_at DESC);
