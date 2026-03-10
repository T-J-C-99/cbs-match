import { NextResponse } from "next/server";
import { apiBaseUrl, applyRefreshCookie, getAccessTokenFromRequest, tenantHeader } from "@/lib/server-api";
import { safeProxyJson } from "@/lib/route-proxy";

export async function POST(req: Request, { params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  const authState = await getAccessTokenFromRequest(req);
  if (!authState.accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();
  const proxied = await safeProxyJson(async () => {
    const res = await fetch(`${apiBaseUrl()}/sessions/${sessionId}/answers`, {
      method: "POST",
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
  }, "Answer service unavailable");

  const response = new NextResponse(proxied.body, {
    status: proxied.status,
    headers: { "Content-Type": "application/json" },
  });
  applyRefreshCookie(response, authState.rotatedRefreshToken);
  return response;
}