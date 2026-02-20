CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS survey_session (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  survey_slug TEXT NOT NULL,
  survey_version INT NOT NULL,
  status TEXT NOT NULL DEFAULT 'in_progress',
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS survey_answer (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES survey_session(id) ON DELETE CASCADE,
  question_code TEXT NOT NULL,
  answer_value JSONB NOT NULL,
  answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_session_question UNIQUE(session_id, question_code)
);

CREATE INDEX IF NOT EXISTS idx_survey_answer_session_id ON survey_answer(session_id);
CREATE INDEX IF NOT EXISTS idx_survey_answer_question_code ON survey_answer(question_code);

CREATE TABLE IF NOT EXISTS user_traits (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  survey_slug TEXT NOT NULL,
  survey_version INT NOT NULL,
  traits JSONB NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_user_traits_version UNIQUE(user_id, survey_slug, survey_version)
);
