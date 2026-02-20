import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function GET(req: Request, ctx: { params: Promise<{ week: string }> }) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { week } = await ctx.params;
  const qs = new URL(req.url).searchParams.toString();
  const res = await fetch(`${apiBaseUrl()}/admin/matches/week/${week}${qs ? `?${qs}` : ""}`, {
    headers,
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
