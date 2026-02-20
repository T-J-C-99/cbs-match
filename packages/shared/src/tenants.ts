import tenantDefinitions from "./tenants.json";

export type TenantSlug = "cbs" | "hbs" | "gsb" | "wharton" | "kellogg" | "booth" | "sloan";

export type TenantTheme = {
  primary: string;
  secondary: string;
  accent: string;
  bg: string;
  text: string;
  muted: string;
};

export type TenantConfig = {
  slug: TenantSlug;
  name: string;
  tagline: string;
  emailDomains: string[];
  theme: TenantTheme;
};

const TENANTS = tenantDefinitions as TenantConfig[];

export const DEFAULT_TENANT_SLUG: TenantSlug = "cbs";

export function getTenants(): TenantConfig[] {
  return TENANTS;
}

export function getTenantBySlug(slug: string | null | undefined): TenantConfig | undefined {
  if (!slug) return undefined;
  return TENANTS.find((t) => t.slug === slug);
}

export function getDefaultTenant(): TenantConfig {
  return getTenantBySlug(DEFAULT_TENANT_SLUG) ?? TENANTS[0];
}

export function inferTenantFromEmail(email: string): TenantConfig | undefined {
  const value = String(email || "").trim().toLowerCase();
  const domain = value.includes("@") ? value.split("@").pop() || "" : "";
  if (!domain) return undefined;
  const matches = TENANTS.filter((tenant) => tenant.emailDomains.map((d) => d.toLowerCase()).includes(domain));
  if (matches.length === 1) return matches[0];
  return undefined;
}
