import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function requireAdminAccessOrThrow() {
  const headers = await adminAuthHeaders();
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    throw new Error("Forbidden: missing admin session");
  }
  const res = await fetch(`${apiBaseUrl()}/admin/auth/me`, { headers, cache: "no-store" });
  if (!res.ok) {
    throw new Error("Forbidden: invalid or expired admin session");
  }
}
