import { cookies } from "next/headers";
import { type TenantConfig } from "@cbs-match/shared";
import { TENANT_COOKIE, getTenantFromSlug } from "@/lib/tenant";

export async function getTenantFromRequestCookie(): Promise<TenantConfig> {
  const slug = (await cookies()).get(TENANT_COOKIE)?.value;
  return getTenantFromSlug(slug);
}
