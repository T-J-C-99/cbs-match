"use client";

import Link from "next/link";
import { clearTenantClientContext } from "@/lib/tenant";

export default function ChangeCommunityLink({ className }: { className?: string }) {
  return (
    <Link
      href="/choose"
      className={className || "text-xs font-medium text-[var(--brand-muted)] underline"}
      onClick={() => clearTenantClientContext()}
    >
      Change community
    </Link>
  );
}
