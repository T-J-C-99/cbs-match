import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function GET(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const res = await fetch(`${apiBaseUrl()}/admin/calibration/current-week`, {
    headers,
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
