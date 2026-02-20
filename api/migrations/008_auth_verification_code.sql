ALTER TABLE email_verification_token
  ADD COLUMN IF NOT EXISTS code_hash TEXT NULL,
  ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_email_verification_user_code_hash
  ON email_verification_token(user_id, code_hash);
