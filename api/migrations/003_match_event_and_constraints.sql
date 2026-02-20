CREATE TABLE IF NOT EXISTS match_event (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  week_start_date DATE NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_match_event_week ON match_event(week_start_date);
CREATE INDEX IF NOT EXISTS idx_match_event_user ON match_event(user_id);
CREATE INDEX IF NOT EXISTS idx_match_event_type ON match_event(event_type);

CREATE INDEX IF NOT EXISTS idx_weekly_match_history_pair
  ON weekly_match_assignment(user_id, matched_user_id, week_start_date);

ALTER TABLE weekly_match_assignment ALTER COLUMN matched_user_id DROP NOT NULL;
ALTER TABLE weekly_match_assignment ALTER COLUMN score_total DROP NOT NULL;

DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN (
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'weekly_match_assignment'::regclass
      AND contype = 'c'
  ) LOOP
    EXECUTE format('ALTER TABLE weekly_match_assignment DROP CONSTRAINT %I', r.conname);
  END LOOP;
END $$;

ALTER TABLE weekly_match_assignment
  ADD CONSTRAINT chk_weekly_match_status
  CHECK (status IN ('proposed','revealed','accepted','declined','expired','no_match'));

ALTER TABLE weekly_match_assignment
  ADD CONSTRAINT chk_weekly_match_no_match_shape
  CHECK (
    (status = 'no_match' AND matched_user_id IS NULL AND score_total IS NULL)
    OR
    (status <> 'no_match' AND matched_user_id IS NOT NULL AND score_total IS NOT NULL)
  );
