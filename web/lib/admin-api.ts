import { cookies } from "next/headers";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session";

export async function adminAuthHeaders(req?: Request): Promise<Record<string, string>> {
  const incomingAuth = req?.headers.get("authorization");
  if (incomingAuth) return { Authorization: incomingAuth };

  const incomingToken = req?.headers.get("x-admin-token");
  if (incomingToken) return { "X-Admin-Token": incomingToken };

  const token = (await cookies()).get(ADMIN_SESSION_COOKIE)?.value;
  if (token) return { Authorization: `Bearer ${token}` };

  const fallback = process.env.ADMIN_TOKEN;
  if (fallback) return { "X-Admin-Token": fallback };

  return {};
}
