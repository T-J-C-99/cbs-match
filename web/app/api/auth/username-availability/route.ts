import { NextResponse } from "next/server";
import { apiBaseUrl, tenantHeader } from "@/lib/server-api";
import { safeProxyJson } from "@/lib/route-proxy";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const username = searchParams.get("username") || "";
  return safeProxyJson(async () =>
    fetch(`${apiBaseUrl()}/auth/username-availability?username=${encodeURIComponent(username)}`, {
      headers: { ...(await tenantHeader()) },
    }),
    "Could not check username"
  );
}
