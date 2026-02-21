import { z } from "zod";

import { useAppStore } from "../store/appStore";
import { removeSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";

async function performRefresh(): Promise<string | null> {
  const state = useAppStore.getState();
  const refreshToken = state.refreshToken;
  if (!refreshToken) return null;

  const url = `${state.apiBaseUrl.replace(/\/$/, "")}/auth/refresh`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Auth-Mode": "bearer" },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token || !data.refresh_token) {
    state.setAccessToken(null);
    state.setRefreshToken(null);
    state.setUserId(null);
    state.setUserEmail(null);
    state.setIsEmailVerified(false);
    state.setSessionId(null);
    await Promise.all([
      removeSecureItem(STORAGE_KEYS.accessToken),
      removeSecureItem(STORAGE_KEYS.refreshToken),
      removeSecureItem(STORAGE_KEYS.userId),
      removeSecureItem(STORAGE_KEYS.userEmail),
      removeSecureItem(STORAGE_KEYS.isEmailVerified),
      removeSecureItem(STORAGE_KEYS.sessionId)
    ]);
    return null;
  }

  state.setAccessToken(data.access_token);
  state.setRefreshToken(data.refresh_token);
  await Promise.all([
    setSecureItem(STORAGE_KEYS.accessToken, data.access_token),
    setSecureItem(STORAGE_KEYS.refreshToken, data.refresh_token)
  ]);
  return data.access_token as string;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, parser?: z.ZodSchema<T>, allowRetry = true): Promise<T> {
  const state = useAppStore.getState();
  const url = `${state.apiBaseUrl.replace(/\/$/, "")}${path}`;
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined)
  };
  headers["X-Tenant-Slug"] = state.tenantSlug || "cbs";
  const hasContentType = Object.keys(headers).some((k) => k.toLowerCase() === "content-type");
  if (!(init.body instanceof FormData) && !hasContentType) {
    headers["Content-Type"] = "application/json";
  }
  if (state.accessToken) headers["Authorization"] = `Bearer ${state.accessToken}`;

  const res = await fetch(url, { ...init, headers });
  const data = await res.json().catch(() => ({}));

  if (res.status === 401 && allowRetry && !path.startsWith("/auth/")) {
    const refreshed = await performRefresh();
    if (refreshed) {
      return apiRequest(path, init, parser, false);
    }
  }

  if (!res.ok) {
    throw new Error((data as any).detail || `Request failed: ${res.status}`);
  }
  return parser ? parser.parse(data) : (data as T);
}
