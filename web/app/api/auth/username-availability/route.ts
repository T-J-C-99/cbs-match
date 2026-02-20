import { NextResponse } from "next/server";
import { apiBaseUrl, tenantHeader } from "@/lib/server-api";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const username = searchParams.get("username") || "";
  const res = await fetch(`${apiBaseUrl()}/auth/username-availability?username=${encodeURIComponent(username)}`, {
    headers: { ...(await tenantHeader()) },
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
