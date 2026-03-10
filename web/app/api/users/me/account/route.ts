import { NextResponse } from "next/server";
import { apiBaseUrl, applyRefreshCookie, getAccessTokenFromRequest, tenantHeader } from "@/lib/server-api";
import { safeProxyJson } from "@/lib/route-proxy";

export async function DELETE(req: Request) {
  const authState = await getAccessTokenFromRequest(req);
  if (!authState.accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const proxied = await safeProxyJson(async () => {
    const res = await fetch(`${apiBaseUrl()}/users/me/account`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${authState.accessToken}`,
        ...(await tenantHeader()),
      },
    });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  }, "Account service unavailable");

  const response = new NextResponse(proxied.body, {
    status: proxied.status,
    headers: { "Content-Type": "application/json" },
  });
  applyRefreshCookie(response, authState.rotatedRefreshToken);
  return response;
}
