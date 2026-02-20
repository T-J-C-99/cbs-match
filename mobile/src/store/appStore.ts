import { create } from "zustand";

type AppState = {
  tenantSlug: string;
  userId: string | null;
  userEmail: string | null;
  username: string | null;
  isEmailVerified: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  sessionId: string | null;
  hasCompletedSurvey: boolean;
  hasRequiredProfile: boolean;
  apiBaseUrl: string;
  hasOnboarded: boolean;
  setUserId: (value: string | null) => void;
  setUserEmail: (value: string | null) => void;
  setUsername: (value: string | null) => void;
  setIsEmailVerified: (value: boolean) => void;
  setAccessToken: (value: string | null) => void;
  setRefreshToken: (value: string | null) => void;
  setSessionId: (value: string | null) => void;
  setHasCompletedSurvey: (value: boolean) => void;
  setHasRequiredProfile: (value: boolean) => void;
  setApiBaseUrl: (value: string) => void;
  setHasOnboarded: (value: boolean) => void;
  setTenantSlug: (value: string) => void;
};

export const useAppStore = create<AppState>((set) => ({
  tenantSlug: "cbs",
  userId: null,
  userEmail: null,
  username: null,
  isEmailVerified: false,
  accessToken: null,
  refreshToken: null,
  sessionId: null,
  hasCompletedSurvey: false,
  hasRequiredProfile: true,
  apiBaseUrl: "http://localhost:8000",
  hasOnboarded: false,
  setUserId: (userId) => set({ userId }),
  setUserEmail: (userEmail) => set({ userEmail }),
  setUsername: (username) => set({ username }),
  setIsEmailVerified: (isEmailVerified) => set({ isEmailVerified }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setRefreshToken: (refreshToken) => set({ refreshToken }),
  setSessionId: (sessionId) => set({ sessionId }),
  setHasCompletedSurvey: (hasCompletedSurvey) => set({ hasCompletedSurvey }),
  setHasRequiredProfile: (hasRequiredProfile) => set({ hasRequiredProfile }),
  setApiBaseUrl: (apiBaseUrl) => set({ apiBaseUrl }),
  setHasOnboarded: (hasOnboarded) => set({ hasOnboarded }),
  setTenantSlug: (tenantSlug) => set({ tenantSlug: tenantSlug || "cbs" }),
}));
