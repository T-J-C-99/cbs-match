ALTER TABLE user_account
  ADD COLUMN IF NOT EXISTS gender_identity TEXT NULL,
  ADD COLUMN IF NOT EXISTS seeking_genders JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE user_account
  DROP CONSTRAINT IF EXISTS chk_user_account_gender_identity;

ALTER TABLE user_account
  ADD CONSTRAINT chk_user_account_gender_identity
  CHECK (gender_identity IS NULL OR gender_identity IN ('man', 'woman', 'nonbinary', 'other'));

ALTER TABLE user_account
  DROP CONSTRAINT IF EXISTS chk_user_account_seeking_genders_array;

ALTER TABLE user_account
  ADD CONSTRAINT chk_user_account_seeking_genders_array
  CHECK (jsonb_typeof(seeking_genders) = 'array');

ALTER TABLE user_profile
  ADD COLUMN IF NOT EXISTS gender_identity TEXT NULL,
  ADD COLUMN IF NOT EXISTS seeking_genders JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE user_profile
  DROP CONSTRAINT IF EXISTS chk_user_profile_gender_identity;

ALTER TABLE user_profile
  ADD CONSTRAINT chk_user_profile_gender_identity
  CHECK (gender_identity IS NULL OR gender_identity IN ('man', 'woman', 'nonbinary', 'other'));

ALTER TABLE user_profile
  DROP CONSTRAINT IF EXISTS chk_user_profile_seeking_genders_array;

ALTER TABLE user_profile
  ADD CONSTRAINT chk_user_profile_seeking_genders_array
  CHECK (jsonb_typeof(seeking_genders) = 'array');

UPDATE user_profile up
SET
  gender_identity = COALESCE(up.gender_identity, ua.gender_identity),
  seeking_genders = CASE
    WHEN up.seeking_genders IS NULL OR jsonb_typeof(up.seeking_genders) <> 'array' THEN COALESCE(ua.seeking_genders, '[]'::jsonb)
    ELSE up.seeking_genders
  END,
  updated_at = NOW()
FROM user_account ua
WHERE up.user_id = ua.id;
