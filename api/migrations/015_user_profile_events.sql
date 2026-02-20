CREATE TABLE IF NOT EXISTS user_profile_event (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profile_event_user_created
  ON user_profile_event(user_id, created_at DESC);
