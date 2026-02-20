CREATE TABLE IF NOT EXISTS match_feedback (
  id UUID PRIMARY KEY,
  week_start_date DATE NOT NULL,
  user_id UUID NOT NULL,
  matched_user_id UUID NOT NULL,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  answers JSONB NOT NULL,
  CONSTRAINT uq_match_feedback_week_user UNIQUE (week_start_date, user_id)
);

CREATE INDEX IF NOT EXISTS idx_match_feedback_week_user
  ON match_feedback(week_start_date, user_id);

CREATE INDEX IF NOT EXISTS idx_match_feedback_week_matched
  ON match_feedback(week_start_date, matched_user_id);
