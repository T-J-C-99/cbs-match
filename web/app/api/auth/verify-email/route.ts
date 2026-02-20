import { NextResponse } from "next/server";
import { apiBaseUrl, tenantHeader } from "@/lib/server-api";

export async function POST(req: Request) {
  const body = await req.text();
  const res = await fetch(`${apiBaseUrl()}/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await tenantHeader()) },
    body,
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
