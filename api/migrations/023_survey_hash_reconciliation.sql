ALTER TABLE survey_definition
  ADD COLUMN IF NOT EXISTS definition_hash TEXT,
  ADD COLUMN IF NOT EXISTS fingerprint_created_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_survey_definition_definition_hash
  ON survey_definition(definition_hash)
  WHERE definition_hash IS NOT NULL;

ALTER TABLE survey_session
  ADD COLUMN IF NOT EXISTS survey_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_survey_session_user_slug_version_hash
  ON survey_session(user_id, survey_slug, survey_version, survey_hash);

ALTER TABLE user_traits
  ADD COLUMN IF NOT EXISTS computed_for_survey_hash TEXT,
  ADD COLUMN IF NOT EXISTS traits_schema_version INT,
  ADD COLUMN IF NOT EXISTS ocean_scores JSONB,
  ADD COLUMN IF NOT EXISTS insights_json JSONB;

CREATE INDEX IF NOT EXISTS idx_user_traits_user_slug_hash
  ON user_traits(user_id, survey_slug, computed_for_survey_hash);

CREATE TABLE IF NOT EXISTS survey_reconciliation_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  tenant_id UUID NULL REFERENCES tenant(id) ON DELETE SET NULL,
  survey_slug TEXT NOT NULL,
  current_survey_hash TEXT NOT NULL,
  source_survey_hash TEXT NULL,
  source_survey_version INT NULL,
  answers_current JSONB NOT NULL DEFAULT '{}'::jsonb,
  missing_question_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  needs_retake BOOLEAN NOT NULL DEFAULT FALSE,
  migration_report JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_survey_reconciliation_user_slug_hash UNIQUE (user_id, survey_slug, current_survey_hash)
);

CREATE INDEX IF NOT EXISTS idx_survey_reconciliation_tenant_slug
  ON survey_reconciliation_state(tenant_id, survey_slug, updated_at DESC);
