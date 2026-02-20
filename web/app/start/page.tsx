"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function StartInner() {
  const router = useRouter();
  const { fetchWithAuth } = useAuth();

  useEffect(() => {
    const decide = async () => {
      const res = await fetchWithAuth(`${API_BASE}/users/me/state`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        router.replace("/welcome");
        return;
      }
      if (!data?.onboarding?.has_completed_survey) {
        router.replace("/welcome");
        return;
      }
      if (!data?.profile?.has_required_profile) {
        router.replace("/profile?required=1");
        return;
      }
      router.replace("/home");
    };
    decide();
  }, [fetchWithAuth, router]);

  return <div className="mx-auto max-w-2xl p-6">Routing...</div>;
}

export default function StartPage() {
  return (
    <RequireAuth>
      <StartInner />
    </RequireAuth>
  );
}
