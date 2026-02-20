import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { apiBaseUrl, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

export async function POST(req: Request) {
  const contentType = req.headers.get("content-type") || "";

  const res = contentType.includes("multipart/form-data")
    ? await fetch(`${apiBaseUrl()}/auth/register`, {
        method: "POST",
        headers: { ...(await tenantHeader()) },
        body: await req.formData(),
      })
    : await fetch(`${apiBaseUrl()}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
        body: await req.text(),
      });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) return NextResponse.json(data, { status: res.status });

  if (data.refresh_token) {
    (await cookies()).set(REFRESH_COOKIE, data.refresh_token, {
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
  }, { status: res.status });
}
