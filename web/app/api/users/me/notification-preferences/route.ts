import { NextResponse } from "next/server";
import { apiBaseUrl } from "@/lib/server-api";

export async function GET(req: Request) {
  const auth = req.headers.get("authorization");
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${apiBaseUrl()}/users/me/notification-preferences`, {
    headers: { Authorization: auth },
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}

export async function PUT(req: Request) {
  const auth = req.headers.get("authorization");
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const body = await req.text();
  const res = await fetch(`${apiBaseUrl()}/users/me/notification-preferences`, {
    method: "PUT",
    headers: { Authorization: auth, "Content-Type": "application/json" },
    body,
  });
  const data = await res.text();
  return new NextResponse(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}
