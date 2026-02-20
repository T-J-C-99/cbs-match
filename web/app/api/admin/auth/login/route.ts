import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { apiBaseUrl } from "@/lib/server-api";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session";

export async function POST(req: Request) {
  const body = await req.text();
  const res = await fetch(`${apiBaseUrl()}/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(payload, { status: res.status });
  }

  if (payload?.access_token) {
    (await cookies()).set(ADMIN_SESSION_COOKIE, String(payload.access_token), {
      httpOnly: true,
      secure: false,
      sameSite: "lax",
      path: "/",
      maxAge: Number(payload.expires_in || 60 * 60),
    });
  }
  return NextResponse.json(payload);
}
