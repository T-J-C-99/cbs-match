import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ACCESS_COOKIE, apiBaseUrl, authCookieOptions, clearAuthCookies, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

export async function POST() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return NextResponse.json({ detail: "No refresh token" }, { status: 401 });

  const res = await fetch(`${apiBaseUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const response = NextResponse.json(data, { status: res.status });
    clearAuthCookies(response);
    return response;
  }

  const response = NextResponse.json({
    access_token: data.access_token,
    token_type: data.token_type,
    expires_in: data.expires_in,
  });

  if (data.refresh_token) {
    response.cookies.set(REFRESH_COOKIE, data.refresh_token, authCookieOptions());
  }
  if (data.access_token) {
    response.cookies.set(ACCESS_COOKIE, String(data.access_token), {
      ...authCookieOptions(),
      maxAge: 60 * 60,
    });
  }

  return response;
}
