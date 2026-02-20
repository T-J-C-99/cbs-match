CREATE TABLE IF NOT EXISTS vibe_card_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenant(id),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  survey_slug TEXT NOT NULL,
  survey_version INT NOT NULL,
  vibe_version TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, user_id, survey_slug, survey_version, vibe_version)
);

INSERT INTO vibe_card_snapshots (id, tenant_id, user_id, survey_slug, survey_version, vibe_version, payload_json, created_at)
SELECT
  gen_random_uuid(),
  uvc.tenant_id,
  uvc.user_id,
  uvc.survey_slug,
  uvc.survey_version,
  COALESCE(uvc.vibe_json -> 'meta' ->> 'version', 'vibe-card-legacy'),
  uvc.vibe_json,
  uvc.created_at
FROM user_vibe_card uvc
ON CONFLICT (tenant_id, user_id, survey_slug, survey_version, vibe_version) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_vibe_card_snapshots_tenant_created
  ON vibe_card_snapshots(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS analytics_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenant(id),
  user_id UUID NULL REFERENCES user_account(id) ON DELETE SET NULL,
  event_name TEXT NOT NULL,
  properties_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  week_start_date DATE NULL,
  source TEXT NOT NULL DEFAULT 'api'
);

CREATE INDEX IF NOT EXISTS idx_analytics_event_tenant_created
  ON analytics_event(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_event_tenant_week
  ON analytics_event(tenant_id, week_start_date);

CREATE INDEX IF NOT EXISTS idx_analytics_event_tenant_name
  ON analytics_event(tenant_id, event_name);

CREATE TABLE IF NOT EXISTS notifications_outbox (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenant(id),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  notification_type TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'pending',
  scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  attempt_count INT NOT NULL DEFAULT 0,
  last_error TEXT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_outbox_status_scheduled
  ON notifications_outbox(status, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_notifications_outbox_tenant_created
  ON notifications_outbox(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notifications_in_app (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenant(id),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  notification_type TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_in_app_user_created
  ON notifications_in_app(tenant_id, user_id, created_at DESC);