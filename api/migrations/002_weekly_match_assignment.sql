CREATE TABLE IF NOT EXISTS weekly_match_assignment (
  id UUID PRIMARY KEY,
  week_start_date DATE NOT NULL,
  user_id UUID NOT NULL,
  matched_user_id UUID NOT NULL,
  score_total NUMERIC NOT NULL,
  score_breakdown JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('proposed','revealed','accepted','declined','expired')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_weekly_match_assignment_user_week
  ON weekly_match_assignment(week_start_date, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_weekly_match_assignment_matched_week
  ON weekly_match_assignment(week_start_date, matched_user_id);

CREATE INDEX IF NOT EXISTS idx_weekly_match_assignment_week_start_date
  ON weekly_match_assignment(week_start_date);
CREATE INDEX IF NOT EXISTS idx_weekly_match_assignment_user_id
  ON weekly_match_assignment(user_id);
CREATE INDEX IF NOT EXISTS idx_weekly_match_assignment_matched_user_id
  ON weekly_match_assignment(matched_user_id);
CREATE INDEX IF NOT EXISTS idx_weekly_match_assignment_status
  ON weekly_match_assignment(status);
