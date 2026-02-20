CREATE TABLE IF NOT EXISTS user_vibe_card_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  tenant_id UUID REFERENCES tenant(id),
  survey_slug TEXT NOT NULL,
  survey_version INT NOT NULL,
  vibe_json JSONB NOT NULL,
  saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, survey_slug, survey_version)
);

CREATE INDEX IF NOT EXISTS idx_user_vibe_snapshot_tenant_saved
  ON user_vibe_card_snapshot(tenant_id, saved_at DESC);
