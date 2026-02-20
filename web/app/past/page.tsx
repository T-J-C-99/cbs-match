"use client";

import { useEffect, useState } from "react";
import AppShellNav from "@/components/AppShellNav";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

// Simple icon components for contact methods
function EmailIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}

function PhoneIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type HistoryItem = {
  week_start_date: string;
  status: string;
  matched_profile: {
    id: string | null;
    email: string | null;
    phone_number?: string | null;
    instagram_handle?: string | null;
    display_name: string | null;
    cbs_year: string | null;
    hometown: string | null;
    photo_urls: string[];
  } | null;
  explanation_v2?: {
    overall: string;
  };
};

type CurrentMatchPayload = {
  match: {
    week_start_date: string;
    matched_profile?: { id?: string | null } | null;
  } | null;
};

function statusTone(status: string) {
  const s = status.toLowerCase();
  if (s === "accepted") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (s === "declined") return "border-rose-200 bg-rose-50 text-rose-700";
  if (s === "expired") return "border-amber-200 bg-amber-50 text-amber-700";
  if (s === "no_match" || s === "blocked") return "border-slate-200 bg-slate-50 text-slate-700";
  return "border-cbs-columbia bg-cbs-sky text-cbs-ink";
}

function PastInner() {
  const { fetchWithAuth } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<HistoryItem[]>([]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [historyRes, currentRes] = await Promise.all([
          fetchWithAuth(`${API_BASE}/matches/history?limit=30`),
          fetchWithAuth(`${API_BASE}/matches/current`),
        ]);

        const historyData = await historyRes.json().catch(() => ({}));
        const currentData = (await currentRes.json().catch(() => ({}))) as CurrentMatchPayload;

        if (!historyRes.ok) throw new Error(historyData.detail || "Could not load history");

        const currentWeek = currentData?.match?.week_start_date || null;
        const currentMatchedUserId = currentData?.match?.matched_profile?.id || null;

        const rawHistory = Array.isArray(historyData?.history) ? (historyData.history as HistoryItem[]) : [];
        const filteredHistory = rawHistory.filter((item) => {
          if (!currentWeek) return true;
          // Keep Past tab strictly historical: exclude the active current-week assignment.
          if (item.week_start_date !== currentWeek) return true;
          const itemMatchedId = item.matched_profile?.id || null;
          return itemMatchedId !== currentMatchedUserId;
        });

        setItems(filteredHistory);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [fetchWithAuth]);

  return (
    <div className="cbs-page-shell">
      <AppShellNav />
      <h1 className="text-3xl font-semibold text-cbs-ink">Past matches</h1>
      <p className="mt-2 text-sm text-cbs-slate">A compact archive of your prior match cycles.</p>

      {loading && <p className="mt-6 text-sm text-cbs-slate">Loading history...</p>}
      {error && <p className="mt-6 rounded bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}

      {!loading && !error && !items.length && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700 shadow-sm">
          No past cycles yet.
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {items.map((item) => {
          const profile = item.matched_profile;
          const photo = profile?.photo_urls?.[0] || "";
          const name = profile?.display_name || "No match this cycle";
          const year = profile?.cbs_year ? `CBS ${profile.cbs_year}` : null;
          const hometown = profile?.hometown || null;

          return (
            <article
              key={`${item.week_start_date}-${item.status}-${profile?.id || "none"}`}
              className="overflow-hidden rounded-xl border border-cbs-columbia bg-white shadow-sm"
            >
              <div className="grid grid-cols-[minmax(140px,58%)_1fr] items-stretch">
                <div className="h-72 bg-slate-100 sm:h-80">
                  {photo ? (
                    <img src={photo} alt={name} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center px-4 text-xs text-slate-500">No photo</div>
                  )}
                </div>
                <div className="p-3 sm:p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h2 className="text-base font-semibold text-cbs-ink">{name}</h2>
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${statusTone(item.status)}`}>
                      {item.status}
                    </span>
                  </div>

                  <p className="mt-2 text-[11px] uppercase tracking-wide text-cbs-slate">Week of {item.week_start_date}</p>

                  {(year || hometown) && (
                    <p className="mt-2 text-sm text-slate-700">
                      {[year, hometown].filter(Boolean).join(" · ")}
                    </p>
                  )}

                  {/* Contact icons row */}
                  {profile?.id && (
                    <div className="mt-3 flex items-center gap-2">
                      {profile.email && (
                        <a
                          href={`mailto:${profile.email}`}
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-cbs-navy hover:bg-cbs-navy hover:text-white"
                          title={`Email: ${profile.email}`}
                        >
                          <EmailIcon className="h-4 w-4" />
                        </a>
                      )}
                      {profile.phone_number && (
                        <a
                          href={`tel:${profile.phone_number}`}
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-cbs-navy hover:bg-cbs-navy hover:text-white"
                          title={`Call: ${profile.phone_number}`}
                        >
                          <PhoneIcon className="h-4 w-4" />
                        </a>
                      )}
                      {profile.instagram_handle && (
                        <a
                          href={`https://instagram.com/${profile.instagram_handle}`}
                          target="_blank"
                          rel="noreferrer"
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-pink-500 hover:bg-gradient-to-br hover:from-purple-500 hover:via-pink-500 hover:to-orange-400 hover:text-white"
                          title={`Instagram: @${profile.instagram_handle}`}
                        >
                          <InstagramIcon className="h-4 w-4" />
                        </a>
                      )}
                      {!profile.email && !profile.phone_number && !profile.instagram_handle && (
                        <span className="text-xs text-slate-400">No contact info</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

export default function PastPage() {
  return (
    <RequireAuth requireVerified>
      <PastInner />
    </RequireAuth>
  );
}
