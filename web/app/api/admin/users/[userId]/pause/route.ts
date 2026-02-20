import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";
import { adminAuthHeaders } from "@/lib/admin-api";

export async function POST(req: Request, ctx: { params: Promise<{ userId: string }> }) {
  const headers = await adminAuthHeaders(req);
  if (!headers.Authorization && !headers["X-Admin-Token"]) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { userId } = await ctx.params;
  const url = new URL(req.url);
  const pauseMatches = (url.searchParams.get("pause_matches") || "false").toLowerCase() === "true";
  const res = await fetch(
    `${apiBaseUrl()}/admin/users/${encodeURIComponent(userId)}/pause?pause_matches=${pauseMatches ? "true" : "false"}`,
    { method: "POST", headers }
  );
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json" } });
}
