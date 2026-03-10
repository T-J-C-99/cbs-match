import { NextResponse } from "next/server";
import { apiBaseUrl, applyRefreshCookie, getAccessTokenFromRequest, tenantHeader } from "@/lib/server-api";
import { safeProxyJson } from "@/lib/route-proxy";

export async function GET(req: Request) {
  const authState = await getAccessTokenFromRequest(req);
  if (!authState.accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const proxied = await safeProxyJson(async () => {
    const res = await fetch(`${apiBaseUrl()}/users/me/profile`, {
      headers: {
        Authorization: `Bearer ${authState.accessToken}`,
        ...(await tenantHeader()),
      },
      cache: "no-store",
    });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  }, "Profile service unavailable");

  const response = new NextResponse(proxied.body, {
    status: proxied.status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
  applyRefreshCookie(response, authState.rotatedRefreshToken);
  return response;
}

export async function PUT(req: Request) {
  const authState = await getAccessTokenFromRequest(req);
  if (!authState.accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();
  const proxied = await safeProxyJson(async () => {
    const res = await fetch(`${apiBaseUrl()}/users/me/profile`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${authState.accessToken}`,
        "Content-Type": "application/json",
        ...(await tenantHeader()),
      },
      body,
    });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  }, "Profile service unavailable");

  const response = new NextResponse(proxied.body, {
    status: proxied.status,
    headers: { "Content-Type": "application/json" },
  });
  applyRefreshCookie(response, authState.rotatedRefreshToken);
  return response;
}
