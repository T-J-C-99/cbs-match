import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function POST(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const url = new URL(req.url);
  const tenantSlug = url.searchParams.get("tenant_slug")?.trim();
  const force = (url.searchParams.get("force") || "").toLowerCase() === "true";
  const allTenants = (url.searchParams.get("all_tenants") || "").toLowerCase() === "true";

  const target = allTenants
    ? `${apiBaseUrl()}/admin/matches/run-weekly-all?force=${force ? "true" : "false"}`
    : tenantSlug
      ? `${apiBaseUrl()}/admin/matches/run-weekly?tenant_slug=${encodeURIComponent(tenantSlug)}&force=${force ? "true" : "false"}`
      : `${apiBaseUrl()}/admin/matches/run-weekly?force=${force ? "true" : "false"}`;
  const res = await fetch(target, {
    method: "POST",
    headers,
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
