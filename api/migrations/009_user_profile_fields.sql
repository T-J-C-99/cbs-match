ALTER TABLE user_account
  ADD COLUMN IF NOT EXISTS cbs_year TEXT NULL,
  ADD COLUMN IF NOT EXISTS hometown TEXT NULL,
  ADD COLUMN IF NOT EXISTS photo_urls JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE user_account
  DROP CONSTRAINT IF EXISTS chk_user_account_cbs_year;

ALTER TABLE user_account
  ADD CONSTRAINT chk_user_account_cbs_year
  CHECK (cbs_year IS NULL OR cbs_year IN ('26', '27'));
