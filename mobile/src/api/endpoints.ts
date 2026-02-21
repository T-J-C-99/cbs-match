import { apiRequest } from "./client";
import {
  authMeSchema,
  authRegisterResponseSchema,
  authTokenSchema,
  matchHistorySchema,
  matchSchema,
  notificationPreferencesSchema,
  sessionDetailSchema,
  sessionResponseSchema,
  surveySchema,
  userProfileSchema,
  userStateSchema,
  vibeCardSchema,
} from "./schemas";

export const api = {
  register: (
    email: string,
    password: string,
    username?: string,
  ) =>
    apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        ...(username ? { username } : {}),
      }),
      headers: { "X-Auth-Mode": "bearer" }
    }, authRegisterResponseSchema),
  login: (identifier: string, password: string) =>
    apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
      headers: { "X-Auth-Mode": "bearer" }
    }, authTokenSchema),
  verifyEmail: (email: string, code: string) =>
    apiRequest("/auth/verify-email", { method: "POST", body: JSON.stringify({ email, code }) }),
  checkUsernameAvailability: (username: string) =>
    apiRequest<{ username: string; available: boolean }>(`/auth/username-availability?username=${encodeURIComponent(username)}`),
  me: () => apiRequest("/auth/me", {}, authMeSchema),
  userState: () => apiRequest("/users/me/state", {}, userStateSchema),
  getProfile: () => apiRequest("/users/me/profile", {}, userProfileSchema),
  uploadProfilePhoto: (form: FormData) =>
    apiRequest<{ photo_urls: string[] }>("/users/me/profile/photos", {
      method: "POST",
      body: form,
      headers: {}
    }),
  updateProfile: (payload: {
    display_name: string;
    cbs_year: string;
    hometown: string;
    phone_number?: string | null;
    instagram_handle?: string | null;
    gender_identity?: string | null;
    seeking_genders?: string[];
    photo_urls: string[];
  }) => apiRequest("/users/me/profile", { method: "PUT", body: JSON.stringify(payload) }, userProfileSchema),
  getPreferences: () => apiRequest<{ preferences: { pause_matches: boolean; updated_at?: string | null } }>("/users/me/preferences"),
  updatePreferences: (pause_matches: boolean) =>
    apiRequest<{ preferences: { pause_matches: boolean; updated_at?: string | null } }>("/users/me/preferences", { method: "PUT", body: JSON.stringify({ pause_matches }) }),
  getNotificationPreferences: () => apiRequest("/users/me/notification-preferences", {}, notificationPreferencesSchema),
  updateNotificationPreferences: (payload: {
    email_enabled: boolean;
    push_enabled: boolean;
    quiet_hours_start_local?: string | null;
    quiet_hours_end_local?: string | null;
    timezone: string;
  }) => apiRequest("/users/me/notification-preferences", { method: "PUT", body: JSON.stringify(payload) }, notificationPreferencesSchema),
  getVibeCard: () => apiRequest("/users/me/vibe-card", {}, vibeCardSchema),
  saveVibeCard: () => apiRequest("/users/me/vibe-card/save", { method: "POST" }),
  trackEvent: (event_name: string, properties?: Record<string, unknown>, week_start_date?: string) =>
    apiRequest("/events/track", {
      method: "POST",
      body: JSON.stringify({ event_name, properties: properties || {}, ...(week_start_date ? { week_start_date } : {}) }),
    }),
  sendDevFeedback: (message: string) =>
    apiRequest<{ feedback: { id: string } }>("/users/me/support/feedback", { method: "POST", body: JSON.stringify({ message }) }),

  getSurvey: () => apiRequest("/survey/active", {}, surveySchema),
  createSession: () => apiRequest("/sessions", { method: "POST" }, sessionResponseSchema),
  getSession: (sessionId: string) => apiRequest(`/sessions/${sessionId}`, {}, sessionDetailSchema),
  saveAnswers: (sessionId: string, answers: Array<{ question_code: string; answer_value: unknown }>) =>
    apiRequest(`/sessions/${sessionId}/answers`, { method: "POST", body: JSON.stringify({ answers }) }),
  completeSession: (sessionId: string) => apiRequest(`/sessions/${sessionId}/complete`, { method: "POST" }),

  getCurrentMatch: () => apiRequest("/matches/current", {}, matchSchema),
  getMatchHistory: (limit = 12) => apiRequest(`/matches/history?limit=${limit}`, {}, matchHistorySchema),
  submitFeedback: (answers: Record<string, unknown>) =>
    apiRequest("/matches/current/feedback", { method: "POST", body: JSON.stringify({ answers }) }),

  blockUser: (blocked_user_id: string) =>
    apiRequest("/safety/block", { method: "POST", body: JSON.stringify({ blocked_user_id }) }),
  reportCurrentMatch: (reason: string, details?: string) =>
    apiRequest("/safety/report", { method: "POST", body: JSON.stringify({ reason, details }) }),
  deleteAccount: () => apiRequest("/users/me/account", { method: "DELETE" }),
};
