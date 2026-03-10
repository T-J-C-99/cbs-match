import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { apiBaseUrl, authCookieOptions, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";
import { safeProxyJson } from "@/lib/route-proxy";

export async function POST(req: Request) {
  const contentType = req.headers.get("content-type") || "";
  let data: any = {};
  const proxied = await safeProxyJson(async () => {
    const res = contentType.includes("multipart/form-data")
      ? await fetch(`${apiBaseUrl()}/auth/register`, {
          method: "POST",
          headers: { "X-Auth-Mode": "bearer", ...(await tenantHeader()) },
          body: await req.formData(),
        })
      : await fetch(`${apiBaseUrl()}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Auth-Mode": "bearer", ...(await tenantHeader()) },
          body: await req.text(),
        });
    data = await res.json().catch(() => ({}));
    return new Response(JSON.stringify(data), { status: res.status, headers: { "Content-Type": "application/json" } });
  }, "Registration service unavailable");

  if (proxied.status >= 500) {
    return proxied;
  }
  const res = proxied;
  if (!res.ok) return NextResponse.json(data, { status: res.status });

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

  const response = NextResponse.json({
    access_token: data.access_token,
    token_type: data.token_type,
    expires_in: data.expires_in,
    user,
  }, { status: res.status });

  if (data.refresh_token) {
    response.cookies.set(REFRESH_COOKIE, data.refresh_token, authCookieOptions());
  }

  return response;
}
