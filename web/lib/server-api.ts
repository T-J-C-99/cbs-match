import { cookies } from "next/headers";
import { TENANT_COOKIE } from "@/lib/tenant";
import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";
import type { NextResponse } from "next/server";

export const REFRESH_COOKIE = "cbs_refresh_token";

export function authCookieOptions(): Partial<ResponseCookie> {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  };
}

export function apiBaseUrl() {
  const url = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
  if (url) return url;
  if (process.env.NODE_ENV !== "production") return "http://localhost:8000";
  throw new Error("Missing API_BASE_URL (or NEXT_PUBLIC_API_BASE_URL) in production");
}

export async function getRefreshTokenFromCookie() {
  return (await cookies()).get(REFRESH_COOKIE)?.value || null;
}

export async function getTenantSlugFromCookie() {
  return (await cookies()).get(TENANT_COOKIE)?.value || "cbs";
}

export async function tenantHeader() {
  return { "X-Tenant-Slug": await getTenantSlugFromCookie() };
}

export async function getAccessTokenFromRequest(req: Request): Promise<{
  accessToken: string | null;
  rotatedRefreshToken: string | null;
}> {
  const auth = req.headers.get("authorization");
  const bearer = auth?.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : null;
  if (bearer) {
    return { accessToken: bearer, rotatedRefreshToken: null };
  }

  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    return { accessToken: null, rotatedRefreshToken: null };
  }

  const res = await fetch(`${apiBaseUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) {
    return { accessToken: null, rotatedRefreshToken: null };
  }

  return {
    accessToken: String(data.access_token),
    rotatedRefreshToken: data.refresh_token ? String(data.refresh_token) : null,
  };
}

export function applyRefreshCookie(response: NextResponse, refreshToken: string | null) {
  if (refreshToken) {
    response.cookies.set(REFRESH_COOKIE, refreshToken, authCookieOptions());
  }
}
