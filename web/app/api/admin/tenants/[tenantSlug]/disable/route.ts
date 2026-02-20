import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function POST(req: Request, ctx: { params: Promise<{ tenantSlug: string }> }) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { tenantSlug } = await ctx.params;
  const res = await fetch(`${apiBaseUrl()}/admin/tenants/${encodeURIComponent(tenantSlug)}/disable`, {
    method: "POST",
    headers,
  });
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json" } });
}
