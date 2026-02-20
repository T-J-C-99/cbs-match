"use client";

import ChangeCommunityLink from "@/components/tenant/ChangeCommunityLink";
import { useAuth } from "@/components/AuthProvider";
import { usePathname } from "next/navigation";

export default function TenantHeaderActions() {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (pathname?.startsWith("/admin")) {
    return null;
  }

  // Keep community switch available for logged-out onboarding only.
  if (loading || user) {
    return null;
  }

  return <ChangeCommunityLink />;
}
