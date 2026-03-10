import { cookies } from "next/headers";
import { TENANT_COOKIE } from "@/lib/tenant";

export const REFRESH_COOKIE = "cbs_refresh_token";

export function apiBaseUrl() {
  const url = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
  if (url) return url;
  if (process.env.NODE_ENV !== "production") return "http://localhost:8000";
  throw new Error("Missing API_BASE_URL (or NEXT_PUBLIC_API_BASE_URL) in production");
}

export async function getRefreshTokenFromCookie() {
  return (await cookies()).get(REFRESH_COOKIE)?.value || null;
}

export async function getTenantSlugFromCookie() {
  return (await cookies()).get(TENANT_COOKIE)?.value || "cbs";
}

export async function tenantHeader() {
  return { "X-Tenant-Slug": await getTenantSlugFromCookie() };
}
