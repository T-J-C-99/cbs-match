"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type VibeCard = {
  title?: string;
  three_bullets?: string[];
  one_watchout?: string;
  best_date_energy?: { label?: string };
  opener_style?: { template?: string };
  compatibility_motto?: string;
};

function DoneInner() {
  const router = useRouter();
  const { fetchWithAuth } = useAuth();
  const [loading, setLoading] = useState(true);
  const [vibeCard, setVibeCard] = useState<VibeCard | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchWithAuth(`${API_BASE}/users/me/vibe-card`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setVibeCard(null);
          return;
        }
        setVibeCard((data?.vibe || null) as VibeCard | null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [fetchWithAuth]);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col justify-center px-6 py-12">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cbs-slate">Survey complete</p>
      <h1 className="mt-2 text-3xl font-semibold text-cbs-ink">Your Vibe Card is ready ✨</h1>
      <p className="mt-2 text-sm text-slate-600">Here’s your immediate readout before you continue into the app.</p>

      <div className="mt-6 rounded-xl border border-cbs-columbia bg-white p-5 shadow-sm">
        {loading ? (
          <p className="text-sm text-slate-600">Loading your vibe card...</p>
        ) : vibeCard ? (
          <>
            <h2 className="text-lg font-semibold text-cbs-ink">{vibeCard.title || "Your dating profile"}</h2>
            <ul className="mt-3 space-y-1.5 text-sm text-slate-700">
              {(vibeCard.three_bullets || []).slice(0, 3).map((line) => (
                <li key={line}>• {line}</li>
              ))}
            </ul>
            {vibeCard.one_watchout ? <p className="mt-3 text-sm text-slate-700"><span className="font-medium text-cbs-ink">Watchout:</span> {vibeCard.one_watchout}</p> : null}
            {vibeCard.best_date_energy?.label ? (
              <p className="mt-1 text-sm text-slate-700"><span className="font-medium text-cbs-ink">Best date energy:</span> {vibeCard.best_date_energy.label}</p>
            ) : null}
            {vibeCard.opener_style?.template ? (
              <p className="mt-1 text-sm text-slate-700"><span className="font-medium text-cbs-ink">Opener style:</span> {vibeCard.opener_style.template}</p>
            ) : null}
            {vibeCard.compatibility_motto ? <p className="mt-3 text-sm text-cbs-slate">{vibeCard.compatibility_motto}</p> : null}
          </>
        ) : (
          <p className="text-sm text-slate-600">Your vibe card is being prepared. Continue and it will appear in Profile shortly.</p>
        )}
      </div>

      <button
        type="button"
        onClick={() => router.push("/start")}
        className="mt-6 w-full rounded bg-black px-4 py-3 font-medium text-white"
      >
        Continue
      </button>
    </div>
  );
}

export default function DonePage() {
  return (
    <RequireAuth requireCompletedSurvey>
      <DoneInner />
    </RequireAuth>
  );
}
