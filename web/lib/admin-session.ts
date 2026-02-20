import { cookies } from "next/headers";

export const ADMIN_SESSION_COOKIE = "cbs_admin_session";

export async function getAdminSessionToken(): Promise<string | null> {
  return (await cookies()).get(ADMIN_SESSION_COOKIE)?.value || null;
}
