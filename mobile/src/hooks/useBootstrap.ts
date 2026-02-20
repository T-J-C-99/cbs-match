import { useEffect, useState } from "react";

import { api } from "../api/endpoints";
import { useAppStore } from "../store/appStore";
import { defaultApiBaseUrl } from "../utils/apiBaseUrl";
import { getSecureItem, removeSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";

export function useBootstrap() {
  const [ready, setReady] = useState(false);
  const hasOnboarded = useAppStore((s) => s.hasOnboarded);
  const accessToken = useAppStore((s) => s.accessToken);
  const setHasOnboarded = useAppStore((s) => s.setHasOnboarded);
  const setUserId = useAppStore((s) => s.setUserId);
  const setUserEmail = useAppStore((s) => s.setUserEmail);
  const setUsername = useAppStore((s) => s.setUsername);
  const setIsEmailVerified = useAppStore((s) => s.setIsEmailVerified);
  const setAccessToken = useAppStore((s) => s.setAccessToken);
  const setRefreshToken = useAppStore((s) => s.setRefreshToken);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const setHasCompletedSurvey = useAppStore((s) => s.setHasCompletedSurvey);
  const setHasRequiredProfile = useAppStore((s) => s.setHasRequiredProfile);
  const setApiBaseUrl = useAppStore((s) => s.setApiBaseUrl);
  const setTenantSlug = useAppStore((s) => s.setTenantSlug);

  useEffect(() => {
    (async () => {
      const [sessionId, completedSurveyRaw, requiredProfileRaw, onboardedRaw, storedBase, access, refresh, userEmail, userId, usernameRaw, tenantSlugRaw, isVerifiedRaw] = await Promise.all([
        getSecureItem(STORAGE_KEYS.sessionId),
        getSecureItem(STORAGE_KEYS.hasCompletedSurvey),
        getSecureItem(STORAGE_KEYS.hasRequiredProfile),
        getSecureItem(STORAGE_KEYS.hasOnboarded),
        getSecureItem(STORAGE_KEYS.apiBaseUrl),
        getSecureItem(STORAGE_KEYS.accessToken),
        getSecureItem(STORAGE_KEYS.refreshToken),
        getSecureItem(STORAGE_KEYS.userEmail),
        getSecureItem(STORAGE_KEYS.userId),
        getSecureItem(STORAGE_KEYS.username),
        getSecureItem(STORAGE_KEYS.tenantSlug),
        getSecureItem(STORAGE_KEYS.isEmailVerified)
      ]);

      setUserId(userId || null);
      setUserEmail(userEmail || null);
      setUsername(usernameRaw || null);
      setIsEmailVerified(isVerifiedRaw === "true");
      setAccessToken(access || null);
      setRefreshToken(refresh || null);
      setSessionId(sessionId || null);
      setHasCompletedSurvey(completedSurveyRaw === "true");
      setHasRequiredProfile(requiredProfileRaw !== "false");
      setApiBaseUrl(storedBase || defaultApiBaseUrl());
      setTenantSlug(tenantSlugRaw || "cbs");
      setHasOnboarded(onboardedRaw === "true");

      if (access) {
        try {
          const [userState, me] = await Promise.all([api.userState(), api.me()]);
          const hasCompleted = userState.onboarding.has_completed_survey;
          const activeSessionId = hasCompleted ? null : userState.onboarding.active_session_id;
          const hasRequiredProfile = userState.profile?.has_required_profile ?? true;
          setUsername(me.username ?? null);
          setHasCompletedSurvey(hasCompleted);
          setHasRequiredProfile(hasRequiredProfile);
          setSessionId(activeSessionId);
          await Promise.all([
            me.username ? setSecureItem(STORAGE_KEYS.username, me.username) : removeSecureItem(STORAGE_KEYS.username),
            setSecureItem(STORAGE_KEYS.hasCompletedSurvey, String(hasCompleted)),
            setSecureItem(STORAGE_KEYS.hasRequiredProfile, String(hasRequiredProfile)),
            activeSessionId
              ? setSecureItem(STORAGE_KEYS.sessionId, activeSessionId)
              : removeSecureItem(STORAGE_KEYS.sessionId),
          ]);
        } catch {
          // keep local bootstrap state if network/auth refresh is unavailable
        }
      }

      setReady(true);
    })();
  }, [setAccessToken, setApiBaseUrl, setHasCompletedSurvey, setHasOnboarded, setHasRequiredProfile, setIsEmailVerified, setRefreshToken, setSessionId, setTenantSlug, setUserEmail, setUserId, setUsername]);

  return { ready, hasOnboarded, hasAuth: Boolean(accessToken) };
}
