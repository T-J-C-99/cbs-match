import type { CSSProperties } from "react";
import type { TenantConfig } from "@cbs-match/shared";

export function tenantCssVars(tenant: TenantConfig): CSSProperties {
  return {
    ["--brand-primary" as string]: tenant.theme.primary,
    ["--brand-secondary" as string]: tenant.theme.secondary,
    ["--brand-accent" as string]: tenant.theme.accent,
    ["--brand-bg" as string]: tenant.theme.bg,
    ["--brand-text" as string]: tenant.theme.text,
    ["--brand-muted" as string]: tenant.theme.muted,
  } as CSSProperties;
}
