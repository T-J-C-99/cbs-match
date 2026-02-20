import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session";

export async function POST(req: Request) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ ok: true });
  }
  const res = await fetch(`${apiBaseUrl()}/admin/auth/logout`, { method: "POST", headers });
  (await cookies()).delete(ADMIN_SESSION_COOKIE);
  const body = await res.text();
  return new NextResponse(body || JSON.stringify({ ok: true }), {
    status: res.ok ? 200 : res.status,
    headers: { "Content-Type": "application/json" },
  });
}
