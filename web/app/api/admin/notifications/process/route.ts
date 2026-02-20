import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function POST(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const url = new URL(req.url);
  const limit = url.searchParams.get("limit") || "100";
  const tenantSlug = (url.searchParams.get("tenant_slug") || "").trim();
  const qs = new URLSearchParams({ limit });
  if (tenantSlug) qs.set("tenant_slug", tenantSlug);
  const res = await fetch(`${apiBaseUrl()}/admin/notifications/process?${qs.toString()}`, {
    method: "POST",
    headers,
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
