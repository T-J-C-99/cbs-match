ALTER TABLE user_account
  ADD COLUMN IF NOT EXISTS username TEXT NULL;

DROP INDEX IF EXISTS uq_user_account_username_lower;
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_account_username_lower
  ON user_account (LOWER(username))
  WHERE username IS NOT NULL;

ALTER TABLE user_account
  DROP CONSTRAINT IF EXISTS chk_user_account_username;

ALTER TABLE user_account
  ADD CONSTRAINT chk_user_account_username
  CHECK (
    username IS NULL
    OR username ~ '^[a-z0-9_]{3,24}$'
  );
