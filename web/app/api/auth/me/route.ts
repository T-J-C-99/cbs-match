import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ACCESS_COOKIE, apiBaseUrl, authCookieOptions, clearAuthCookies, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

async function callMe(accessToken: string) {
  return fetch(`${apiBaseUrl()}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}`, ...(await tenantHeader()) },
  });
}

async function refreshFromCookie() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;

  const res = await fetch(`${apiBaseUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) return null;

  return {
    accessToken: String(data.access_token),
    refreshToken: data.refresh_token ? String(data.refresh_token) : null,
  };
}

export async function GET(req: Request) {
  const auth = req.headers.get("authorization");
  let accessToken = auth?.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : null;
  let rotatedRefreshToken: string | null = null;
  if (!accessToken) {
    const refreshed = await refreshFromCookie();
    accessToken = refreshed?.accessToken ?? null;
    rotatedRefreshToken = refreshed?.refreshToken ?? null;
  }
  if (!accessToken) return NextResponse.json({ user: null }, { status: 401 });

  const res = await callMe(accessToken);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // If tenant context changed in browser but refresh/session cookies are for a different tenant,
    // return a clean unauthenticated state and clear refresh cookie so UX can re-login gracefully.
    if (res.status === 403 || res.status === 401) {
      const response = NextResponse.json({ user: null }, { status: 401 });
      clearAuthCookies(response);
      return response;
    }
    return NextResponse.json({ user: null }, { status: res.status });
  }

  const response = NextResponse.json({ user: data, access_token: accessToken });
  if (accessToken) {
    response.cookies.set(ACCESS_COOKIE, accessToken, {
      ...authCookieOptions(),
      maxAge: 60 * 60,
    });
  }
  if (rotatedRefreshToken) {
    response.cookies.set(REFRESH_COOKIE, rotatedRefreshToken, authCookieOptions());
  }
  return response;
}
