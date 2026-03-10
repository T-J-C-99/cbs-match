"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

function StartInner() {
  const router = useRouter();
  const { fetchWithAuth } = useAuth();

  useEffect(() => {
    const decide = async () => {
      const res = await fetchWithAuth(`/api/users/me/state`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        router.replace("/welcome");
        return;
      }
      if (!data?.onboarding?.has_completed_survey) {
        if (data?.onboarding?.active_session_id) {
          router.replace(`/survey/${data.onboarding.active_session_id}`);
          return;
        }

        const sessionRes = await fetchWithAuth(`/api/sessions`, { method: "POST" });
        const sessionData = await sessionRes.json().catch(() => ({}));
        if (sessionRes.ok && sessionData?.session_id) {
          router.replace(`/survey/${sessionData.session_id}`);
          return;
        }

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
