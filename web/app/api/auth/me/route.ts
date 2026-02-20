import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { apiBaseUrl, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

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

  if (data.refresh_token) {
    (await cookies()).set(REFRESH_COOKIE, data.refresh_token, {
      httpOnly: true,
      secure: false,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }

  return String(data.access_token);
}

export async function GET(req: Request) {
  const auth = req.headers.get("authorization");
  let accessToken = auth?.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : null;
  if (!accessToken) {
    accessToken = await refreshFromCookie();
  }
  if (!accessToken) return NextResponse.json({ user: null }, { status: 401 });

  const res = await callMe(accessToken);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // If tenant context changed in browser but refresh/session cookies are for a different tenant,
    // return a clean unauthenticated state and clear refresh cookie so UX can re-login gracefully.
    if (res.status === 403 || res.status === 401) {
      (await cookies()).delete(REFRESH_COOKIE);
      return NextResponse.json({ user: null }, { status: 401 });
    }
    return NextResponse.json({ user: null }, { status: res.status });
  }
  return NextResponse.json({ user: data, access_token: accessToken });
}
