import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function POST(req: Request, ctx: { params: Promise<{ reportId: string }> }) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { reportId } = await ctx.params;
  const body = await req.text();
  const res = await fetch(`${apiBaseUrl()}/admin/reports/${encodeURIComponent(reportId)}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, { status: res.status, headers: { "Content-Type": "application/json" } });
}
