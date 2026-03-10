import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { apiBaseUrl, clearAuthCookies, REFRESH_COOKIE, tenantHeader } from "@/lib/server-api";

export async function POST() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    await fetch(`${apiBaseUrl()}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => null);
  }

  const response = NextResponse.json({ message: "Logged out" });
  clearAuthCookies(response);
  return response;
}
