import { getDefaultTenant, getTenantBySlug, getTenants, type TenantConfig, type TenantSlug } from "@cbs-match/shared";

export const TENANT_COOKIE = "tenant_slug";

export function getTenantFromSlug(slug: string | null | undefined): TenantConfig {
  return getTenantBySlug(slug || undefined) ?? getDefaultTenant();
}

export function getTenantFromClientStorage(): TenantConfig {
  if (typeof window === "undefined") return getDefaultTenant();
  const slug = window.localStorage.getItem(TENANT_COOKIE);
  return getTenantFromSlug(slug);
}

export function allTenants(): TenantConfig[] {
  return getTenants();
}

export function setTenantClientContext(slug: TenantSlug) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TENANT_COOKIE, slug);
  document.cookie = `${TENANT_COOKIE}=${slug}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
}

export function clearTenantClientContext() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TENANT_COOKIE);
  document.cookie = `${TENANT_COOKIE}=; path=/; max-age=0; samesite=lax`;
}
