import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const TENANT_COOKIE = "tenant_slug";
const ADMIN_COOKIE = "cbs_admin_session";
const KNOWN_TENANTS = new Set(["cbs", "hbs", "gsb", "wharton", "kellogg", "booth", "sloan"]);

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin") && request.nextUrl.pathname !== "/admin/login") {
    const adminSession = request.cookies.get(ADMIN_COOKIE)?.value;
    if (!adminSession) {
      const loginUrl = new URL("/admin/login", request.url);
      return NextResponse.redirect(loginUrl);
    }
  }

  const tenant = (request.nextUrl.searchParams.get("tenant") || "").trim().toLowerCase();
  if (!tenant || !KNOWN_TENANTS.has(tenant)) {
    return NextResponse.next();
  }

  const response = NextResponse.next();
  response.cookies.set(TENANT_COOKIE, tenant, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    secure: false,
  });
  return response;
}

export const config = {
  matcher: ["/admin/:path*", "/login", "/register", "/choose", "/landing", "/"],
};
