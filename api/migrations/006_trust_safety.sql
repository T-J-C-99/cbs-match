CREATE TABLE IF NOT EXISTS user_block (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  blocked_user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_user_block UNIQUE (user_id, blocked_user_id),
  CONSTRAINT chk_user_block_no_self CHECK (user_id <> blocked_user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_block_user_id ON user_block(user_id);
CREATE INDEX IF NOT EXISTS idx_user_block_blocked_user_id ON user_block(blocked_user_id);

CREATE TABLE IF NOT EXISTS match_report (
  id UUID PRIMARY KEY,
  week_start_date DATE NOT NULL,
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  matched_user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  details TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_match_report_week_start_date ON match_report(week_start_date);
CREATE INDEX IF NOT EXISTS idx_match_report_user_id ON match_report(user_id);
CREATE INDEX IF NOT EXISTS idx_match_report_matched_user_id ON match_report(matched_user_id);
