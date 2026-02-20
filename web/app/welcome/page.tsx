"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type UserState = {
  onboarding: {
    has_any_session: boolean;
    has_completed_survey: boolean;
    active_session_id: string | null;
  };
  profile?: {
    has_required_profile: boolean;
  };
};

function WelcomeInner() {
  const router = useRouter();
  const { user, fetchWithAuth } = useAuth();
  const [state, setState] = useState<UserState | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNewUser = useMemo(() => !state?.onboarding?.has_any_session, [state]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetchWithAuth(`${API_BASE}/users/me/state`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Could not load user state");
        setState(data);
        if (data?.onboarding?.has_completed_survey) {
          if (!data?.profile?.has_required_profile) {
            router.replace("/profile?required=1");
          } else {
            router.replace("/home");
          }
          return;
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [fetchWithAuth, router]);

  const startSurvey = async () => {
    setError(null);
    setStarting(true);
    try {
      if (state?.onboarding?.active_session_id) {
        router.push(`/survey/${state.onboarding.active_session_id}`);
        return;
      }
      const res = await fetchWithAuth(`${API_BASE}/sessions`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not create session");
      router.push(`/survey/${data.session_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return <div className="mx-auto max-w-2xl p-6">Loading...</div>;
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col justify-center px-6 py-12">
      <h1 className="text-3xl font-semibold">Welcome{user?.email ? `, ${user.email.split("@")[0]}` : ""}</h1>
      <p className="mt-3 text-slate-600">
        {isNewUser
          ? "Before matching begins, complete your onboarding survey. This survey is required and cannot be skipped."
          : "You have an in-progress survey session. Continue where you left off to unlock your home experience."}
      </p>

      <div className="mt-8 rounded border border-slate-200 bg-white p-5">
        <h2 className="font-medium">How this works</h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>Complete the required survey once to establish your matching profile.</li>
          <li>We compute your traits and compatibility signals.</li>
          <li>You land in your stable home with matches, chat, and profile.</li>
        </ul>
      </div>

      {error && <p className="mt-5 rounded bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}

      <button
        className="mt-6 w-full rounded bg-black px-4 py-3 font-medium text-white disabled:opacity-60"
        onClick={startSurvey}
        disabled={starting}
      >
        {starting ? "Preparing..." : state?.onboarding?.active_session_id ? "Resume survey" : "Start required survey"}
      </button>
    </div>
  );
}

export default function WelcomePage() {
  return (
    <RequireAuth requireVerified>
      <WelcomeInner />
    </RequireAuth>
  );
}
