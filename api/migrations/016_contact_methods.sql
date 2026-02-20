ALTER TABLE user_account
  ADD COLUMN IF NOT EXISTS phone_number TEXT NULL,
  ADD COLUMN IF NOT EXISTS instagram_handle TEXT NULL;

ALTER TABLE user_profile
  ADD COLUMN IF NOT EXISTS phone_number TEXT NULL,
  ADD COLUMN IF NOT EXISTS instagram_handle TEXT NULL;

UPDATE user_profile up
SET
  phone_number = COALESCE(up.phone_number, ua.phone_number),
  instagram_handle = COALESCE(up.instagram_handle, ua.instagram_handle),
  updated_at = NOW()
FROM user_account ua
WHERE up.user_id = ua.id;
