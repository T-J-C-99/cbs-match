import { cookies } from "next/headers";
import { TENANT_COOKIE } from "@/lib/tenant";

export const REFRESH_COOKIE = "cbs_refresh_token";

export function apiBaseUrl() {
  return process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
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
