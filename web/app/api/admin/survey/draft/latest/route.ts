import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function GET(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const res = await fetch(`${apiBaseUrl()}/admin/survey/draft/latest`, {
    headers,
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export async function PUT(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const body = await req.text();
  const res = await fetch(`${apiBaseUrl()}/admin/survey/draft/latest`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...headers },
    body,
    cache: "no-store",
  });
  const textBody = await res.text();
  return new NextResponse(textBody, { status: res.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
