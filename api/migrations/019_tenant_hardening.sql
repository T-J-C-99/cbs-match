ALTER TABLE tenant
  ADD COLUMN IF NOT EXISTS theme JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
DECLARE cbs_id UUID;
BEGIN
  SELECT id INTO cbs_id FROM tenant WHERE slug = 'cbs' LIMIT 1;

  UPDATE user_account
  SET tenant_id = cbs_id
  WHERE tenant_id IS NULL
    AND cbs_id IS NOT NULL;

  IF cbs_id IS NOT NULL THEN
    EXECUTE format('ALTER TABLE user_account ALTER COLUMN tenant_id SET DEFAULT %L::uuid', cbs_id::text);
  END IF;
END $$;

ALTER TABLE user_account
  ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE user_account
  DROP CONSTRAINT IF EXISTS user_account_email_key;

DROP INDEX IF EXISTS uq_user_account_email_tenant;
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_account_email_tenant
  ON user_account (tenant_id, LOWER(email));

DROP INDEX IF EXISTS uq_user_account_username_tenant;
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_account_username_tenant
  ON user_account (tenant_id, LOWER(username))
  WHERE username IS NOT NULL;

ALTER TABLE chat_thread ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE match_event ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);
ALTER TABLE user_profile_event ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenant(id);

UPDATE chat_thread t
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE t.tenant_id IS NULL
  AND ua.id = t.participant_a_id;

UPDATE chat_message m
SET tenant_id = t.tenant_id
FROM chat_thread t
WHERE m.tenant_id IS NULL
  AND t.id = m.thread_id;

UPDATE match_event me
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE me.tenant_id IS NULL
  AND ua.id = me.user_id;

UPDATE user_profile_event upe
SET tenant_id = ua.tenant_id
FROM user_account ua
WHERE upe.tenant_id IS NULL
  AND ua.id = upe.user_id;

CREATE INDEX IF NOT EXISTS idx_chat_thread_tenant_created
  ON chat_thread(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_message_tenant_created
  ON chat_message(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_match_event_tenant_created
  ON match_event(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_profile_event_tenant_created
  ON user_profile_event(tenant_id, created_at DESC);
