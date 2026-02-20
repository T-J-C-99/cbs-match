import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { apiBaseUrl, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

export async function POST(req: Request) {
  const body = await req.text();
  const res = await fetch(`${apiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
    body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return NextResponse.json(data, { status: res.status });

  const refreshToken = data.refresh_token;
  if (refreshToken) {
    (await cookies()).set(REFRESH_COOKIE, refreshToken, {
      httpOnly: true,
      secure: false,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }

  // Fetch user data with the new token
  const accessToken = data.access_token;
  let user = null;
  if (accessToken) {
    try {
      const meRes = await fetch(`${apiBaseUrl()}/auth/me`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          ...(await tenantHeader()),
        },
      });
      if (meRes.ok) {
        user = await meRes.json();
      }
    } catch {
      // Ignore errors fetching user data
    }
  }

  return NextResponse.json({
    access_token: data.access_token,
    token_type: data.token_type,
    expires_in: data.expires_in,
    user,
  });
}
