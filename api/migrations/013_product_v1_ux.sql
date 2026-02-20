CREATE TABLE IF NOT EXISTS user_profile (
  user_id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  cbs_year TEXT NULL,
  hometown TEXT NULL,
  photo_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_user_profile_cbs_year CHECK (cbs_year IS NULL OR cbs_year IN ('26', '27')),
  CONSTRAINT chk_user_profile_photo_urls_array CHECK (jsonb_typeof(photo_urls) = 'array')
);

INSERT INTO user_profile (user_id, display_name, cbs_year, hometown, photo_urls, updated_at)
SELECT
  ua.id,
  COALESCE(NULLIF(BTRIM(ua.display_name), ''), SPLIT_PART(ua.email, '@', 1)) AS display_name,
  ua.cbs_year,
  ua.hometown,
  COALESCE(ua.photo_urls, '[]'::jsonb) AS photo_urls,
  NOW()
FROM user_account ua
ON CONFLICT (user_id) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  cbs_year = EXCLUDED.cbs_year,
  hometown = EXCLUDED.hometown,
  photo_urls = EXCLUDED.photo_urls,
  updated_at = NOW();

CREATE TABLE IF NOT EXISTS user_preferences (
  user_id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE,
  pause_matches BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO user_preferences (user_id)
SELECT id FROM user_account
ON CONFLICT (user_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS support_feedback (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_feedback_user_id ON support_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_support_feedback_created_at ON support_feedback(created_at DESC);
