import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { apiBaseUrl, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

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
    (await cookies()).delete(REFRESH_COOKIE);
    return NextResponse.json(data, { status: res.status });
  }

  if (data.refresh_token) {
    (await cookies()).set(REFRESH_COOKIE, data.refresh_token, {
      httpOnly: true,
      secure: false,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }

  return NextResponse.json({
    access_token: data.access_token,
    token_type: data.token_type,
    expires_in: data.expires_in,
  });
}
