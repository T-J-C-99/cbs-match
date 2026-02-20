import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function GET(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const qs = new URL(req.url).searchParams.toString();
  const res = await fetch(`${apiBaseUrl()}/admin/reports${qs ? `?${qs}` : ""}`, { headers });
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json" } });
}
