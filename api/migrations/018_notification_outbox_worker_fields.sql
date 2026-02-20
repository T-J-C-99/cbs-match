ALTER TABLE notification_outbox
  ADD COLUMN IF NOT EXISTS week_start_date DATE NULL,
  ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS attempts INT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_notification_outbox_retry
  ON notification_outbox(status, next_attempt_at);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_week_template
  ON notification_outbox(tenant_id, user_id, week_start_date, template_key);
