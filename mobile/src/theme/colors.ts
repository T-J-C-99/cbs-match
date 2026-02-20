import { getTenantBySlug } from "@cbs-match/shared";
import { useAppStore } from "../store/appStore";

export type AppColors = {
  background: string;
  surface: string;
  primary: string;
  text: string;
  mutedText: string;
  border: string;
  success: string;
  danger: string;
  warningBg: string;
};

const FALLBACK_COLORS: AppColors = {
  background: "#EAF4FA",
  surface: "#FFFFFF",
  primary: "#1D3557",
  text: "#0F2742",
  mutedText: "#5C6B7A",
  border: "#B9D9EB",
  success: "#1F7A5A",
  danger: "#B42318",
  warningBg: "#FFF7E6",
};

export function getColorsForTenant(slug: string | null | undefined): AppColors {
  const tenant = getTenantBySlug(slug || undefined);
  if (!tenant) return FALLBACK_COLORS;
  return {
    background: tenant.theme.bg,
    surface: "#FFFFFF",
    primary: tenant.theme.primary,
    text: tenant.theme.text,
    mutedText: tenant.theme.muted,
    border: tenant.theme.accent,
    success: FALLBACK_COLORS.success,
    danger: FALLBACK_COLORS.danger,
    warningBg: FALLBACK_COLORS.warningBg,
  };
}

export const colors = new Proxy({} as AppColors, {
  get(_target, key: keyof AppColors) {
    const slug = useAppStore.getState().tenantSlug;
    const resolved = getColorsForTenant(slug);
    return resolved[key];
  },
});
