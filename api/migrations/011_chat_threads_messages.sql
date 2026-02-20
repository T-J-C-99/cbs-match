CREATE TABLE IF NOT EXISTS chat_thread (
  id UUID PRIMARY KEY,
  week_start_date DATE NOT NULL,
  participant_a_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  participant_b_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_chat_thread_distinct_participants CHECK (participant_a_id <> participant_b_id),
  CONSTRAINT uq_chat_thread_week_pair UNIQUE (week_start_date, participant_a_id, participant_b_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_thread_participant_a ON chat_thread(participant_a_id);
CREATE INDEX IF NOT EXISTS idx_chat_thread_participant_b ON chat_thread(participant_b_id);
CREATE INDEX IF NOT EXISTS idx_chat_thread_week_start ON chat_thread(week_start_date);

CREATE TABLE IF NOT EXISTS chat_message (
  id UUID PRIMARY KEY,
  thread_id UUID NOT NULL REFERENCES chat_thread(id) ON DELETE CASCADE,
  sender_user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_message_thread_created ON chat_message(thread_id, created_at);
