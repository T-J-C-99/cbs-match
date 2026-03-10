import { NextResponse } from "next/server";

export async function safeProxyJson(
  fn: () => Promise<Response>,
  fallbackMessage = "Backend service unavailable"
) {
  try {
    const res = await fn();
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : fallbackMessage;
    return NextResponse.json({ detail: fallbackMessage, reason: detail }, { status: 502 });
  }
}
