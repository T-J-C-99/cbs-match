import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function POST(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const requestBody = await req.text();
  const res = await fetch(`${apiBaseUrl()}/admin/survey/initialize-from-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: requestBody,
    cache: "no-store",
  });
  const responseBody = await res.text();
  return new NextResponse(responseBody, { status: res.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
