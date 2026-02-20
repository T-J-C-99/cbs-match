CREATE TABLE IF NOT EXISTS survey_definition (
  id UUID PRIMARY KEY,
  slug TEXT NOT NULL,
  version INT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'published')),
  is_active BOOLEAN NOT NULL DEFAULT FALSE,
  definition_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by_user_id UUID NULL REFERENCES user_account(id) ON DELETE SET NULL,
  CONSTRAINT uq_survey_definition_slug_version UNIQUE (slug, version),
  CONSTRAINT chk_survey_definition_active_published CHECK (
    (is_active = FALSE) OR (status = 'published')
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_survey_definition_active_slug
  ON survey_definition(slug)
  WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_survey_definition_slug_status
  ON survey_definition(slug, status);

CREATE TABLE IF NOT EXISTS survey_change_log (
  id UUID PRIMARY KEY,
  survey_definition_id UUID NOT NULL REFERENCES survey_definition(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  actor_user_id UUID NULL REFERENCES user_account(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  diff_summary TEXT NOT NULL,
  diff_json JSONB NULL
);

CREATE INDEX IF NOT EXISTS idx_survey_change_log_survey_definition_id
  ON survey_change_log(survey_definition_id);

CREATE INDEX IF NOT EXISTS idx_survey_change_log_created_at
  ON survey_change_log(created_at DESC);
