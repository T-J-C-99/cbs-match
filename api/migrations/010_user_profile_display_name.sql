ALTER TABLE user_account
  ADD COLUMN IF NOT EXISTS display_name TEXT NULL;
