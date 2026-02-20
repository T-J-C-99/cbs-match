import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { apiBaseUrl, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

export async function POST() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    await fetch(`${apiBaseUrl()}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => null);
  }

  (await cookies()).delete(REFRESH_COOKIE);
  return NextResponse.json({ message: "Logged out" });
}
