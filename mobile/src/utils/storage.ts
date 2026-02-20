import * as SecureStore from "expo-secure-store";

export const STORAGE_KEYS = {
  userId: "cbs_user_id",
  sessionId: "cbs_session_id",
  hasCompletedSurvey: "cbs_has_completed_survey",
  hasRequiredProfile: "cbs_has_required_profile",
  apiBaseUrl: "cbs_api_base_url",
  hasOnboarded: "cbs_has_onboarded",
  accessToken: "cbs_access_token",
  refreshToken: "cbs_refresh_token",
  userEmail: "cbs_user_email",
  username: "cbs_username",
  tenantSlug: "tenant_slug",
  isEmailVerified: "cbs_is_email_verified",
  lastSeenMatchKey: "cbs_last_seen_match_key"
} as const;

export async function getSecureItem(key: string) {
  return SecureStore.getItemAsync(key);
}

export async function setSecureItem(key: string, value: string) {
  return SecureStore.setItemAsync(key, value);
}

export async function removeSecureItem(key: string) {
  return SecureStore.deleteItemAsync(key);
}
