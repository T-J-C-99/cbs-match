export function normalizeAdminTenantSelection(
  value: string | null | undefined,
  validSlugs: string[] = []
): string {
  const raw = String(value ?? "").trim().toLowerCase();
  if (!raw || raw === "all" || raw === "all tenants") return "";
  if (!validSlugs.length) return raw;
  return validSlugs.includes(raw) ? raw : "";
}

export function getTenantScopeParam(selectedTenant: string | null | undefined): string | undefined {
  const normalized = normalizeAdminTenantSelection(selectedTenant);
  return normalized || undefined;
}
