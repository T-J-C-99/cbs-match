"use client";

import { useEffect, useMemo, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import AppShellNav from "@/components/AppShellNav";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type MatchPayload = {
  match: {
    status: string;
    week_start_date: string;
    matched_profile?: {
      id: string;
      email: string;
      phone_number?: string | null;
      instagram_handle?: string | null;
      display_name: string | null;
      cbs_year: string | null;
      hometown: string | null;
      photo_urls: string[];
    } | null;
  } | null;
  message: string;
  explanation_v2?: {
    overall: string;
    pros: string[];
    cons: string[];
    version: string;
  };
  feedback?: { eligible: boolean; already_submitted: boolean; due_met_question: boolean };
};

const FALLBACK_PROS = [
  "You likely have enough overlap to enjoy a first conversation.",
  "The baseline compatibility suggests this is worth exploring in person.",
];
const FALLBACK_CONS = [
  "You may have different defaults around planning and pace.",
  "It helps to set expectations early so follow-through feels easy.",
];

function MatchHero({ profile, onCopy }: { profile: NonNullable<NonNullable<MatchPayload["match"]>["matched_profile"]>; onCopy?: (value: string, label: string) => void }) {
  const photos = profile.photo_urls || [];
  const [activePhoto, setActivePhoto] = useState(0);
  const hasPhotos = photos.length > 0;

  useEffect(() => {
    if (!photos.length) setActivePhoto(0);
    if (activePhoto >= photos.length) setActivePhoto(0);
  }, [activePhoto, photos.length]);

  const displayName = profile.display_name || "Your match";
  const email = profile.email || "";
  const phone = profile.phone_number || "";
  const instagram = profile.instagram_handle || "";

  return (
    <section className="mx-auto mt-6 w-full max-w-5xl overflow-hidden rounded-2xl border border-cbs-columbia bg-white shadow-[0_10px_30px_rgba(15,39,66,0.08)]">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(260px,42%)_1fr]">
        <div className="bg-slate-100 p-4 lg:p-5">
          <div className="relative mx-auto aspect-[4/5] w-full max-w-[340px] overflow-hidden rounded-xl lg:mx-0">
            {hasPhotos ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photos[activePhoto]} alt={`${displayName} photo ${activePhoto + 1}`} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-600">No photo added yet.</div>
            )}
            {hasPhotos && photos.length > 1 && (
              <>
                <button onClick={() => setActivePhoto((i) => (i === 0 ? photos.length - 1 : i - 1))} className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-white/85 px-3 py-2 text-sm font-semibold text-cbs-ink shadow" aria-label="Previous photo">‹</button>
                <button onClick={() => setActivePhoto((i) => (i === photos.length - 1 ? 0 : i + 1))} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-white/85 px-3 py-2 text-sm font-semibold text-cbs-ink shadow" aria-label="Next photo">›</button>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col p-5 lg:p-6">
          <div className="flex-1">
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-cbs-slate">This week&apos;s match</p>
            <h2 className="mt-2 text-2xl font-semibold text-cbs-ink">{displayName}</h2>
            <div className="mt-6 space-y-3 text-sm text-slate-700">
              <p><span className="font-medium text-cbs-ink">CBS Year:</span> {profile.cbs_year || "Not set"}</p>
              <p><span className="font-medium text-cbs-ink">Hometown:</span> {profile.hometown || "Not set"}</p>
            </div>
          </div>

          {/* Sleek contact actions */}
          <div className="mt-6 flex flex-wrap gap-2">
            {email && (
              <a
                href={`mailto:${email}`}
                className="inline-flex items-center gap-2 rounded-full bg-cbs-navy px-4 py-2 text-sm font-medium text-white transition-all hover:bg-cbs-ink"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                </svg>
                Send Email
              </a>
            )}
            {phone && (
              <button
                onClick={() => navigator.clipboard.writeText(phone).then(() => alert(`Phone number copied: ${phone}`))}
                className="inline-flex items-center gap-2 rounded-full border-2 border-cbs-navy px-4 py-2 text-sm font-medium text-cbs-navy transition-all hover:bg-cbs-navy hover:text-white"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
                Get number
              </button>
            )}
            {instagram && (
              <a
                href={`https://instagram.com/${instagram}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-purple-500 via-pink-500 to-orange-400 px-4 py-2 text-sm font-medium text-white transition-all hover:opacity-90"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                </svg>
                @{instagram}
              </a>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function MatchInner() {
  const { fetchWithAuth } = useAuth();
  const [payload, setPayload] = useState<MatchPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [coffeeIntent, setCoffeeIntent] = useState(4);
  const [met, setMet] = useState<"yes" | "no">("no");
  const [notice, setNotice] = useState<string | null>(null);
  const [feedbackSubmittedFor, setFeedbackSubmittedFor] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    const res = await fetchWithAuth(`${API_BASE}/matches/current`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Failed to load match");
      setLoading(false);
      return;
    }
    setPayload(data);
    setError(null);
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const explanation = payload?.explanation_v2;
  const matchKey = `${payload?.match?.week_start_date || "none"}:${payload?.match?.matched_profile?.id || "none"}`;
  const feedbackSubmitted = feedbackSubmittedFor === matchKey || Boolean(payload?.feedback?.already_submitted);
  const matchedProfile = payload?.match?.matched_profile || null;
  const hasMatch = !loading && Boolean(matchedProfile?.id) && payload?.match?.status !== "no_match";
  const email = matchedProfile?.email || "";
  const phone = matchedProfile?.phone_number || "";
  const instagram = matchedProfile?.instagram_handle || "";

  const copyText = async (value: string, label: string) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setNotice(`${label} copied.`);
    } catch {
      setNotice(`Could not copy ${label.toLowerCase()}.`);
    }
  };
  const pros = useMemo(() => Array.from(new Set(explanation?.pros || FALLBACK_PROS)).slice(0, 2), [explanation]);
  const cons = useMemo(() => Array.from(new Set(explanation?.cons || FALLBACK_CONS)).slice(0, 2), [explanation]);
  const deanOverallFallbacks = [
    "The Dean of Dating ran this week’s model and sees strong in-person potential.",
    "The Dean of Dating reads this as a high-upside pairing if you both lean in.",
    "The Dean of Dating sees enough compatibility signals to make this worth the week.",
  ];
  const deanIdx = Math.abs(matchKey.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0)) % deanOverallFallbacks.length;
  const overallCopy = explanation?.overall || payload?.message || deanOverallFallbacks[deanIdx];

  const submitFeedback = async () => {
    const answers: Record<string, unknown> = { coffee_intent: coffeeIntent };
    if (payload?.feedback?.due_met_question) {
      answers.met = met === "yes";
    }
    const res = await fetchWithAuth(`${API_BASE}/matches/current/feedback`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });
    if (res.ok) {
      setFeedbackSubmittedFor(matchKey);
      setNotice("Feedback saved.");
      await load();
    }
  };

  const trackContact = async (channel: "email" | "phone" | "instagram") => {
    try {
      await fetchWithAuth(`${API_BASE}/matches/current/contact-click`, {
        method: "POST",
        body: JSON.stringify({ channel }),
      });
    } catch {
      // best-effort instrumentation
    }
  };

  return (
    <div className="cbs-page-shell">
      <AppShellNav />
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-cbs-ink">
            {loading ? "Your weekly match" : hasMatch ? "Your connection this week" : "No match this week"}
          </h1>
        </div>
        {payload?.match?.week_start_date ? <p className="text-sm text-cbs-slate">Week of {payload.match.week_start_date}</p> : null}
      </header>
      {error && <p className="mb-4 rounded bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}

      {!loading && hasMatch && payload?.match?.matched_profile ? <MatchHero profile={payload.match.matched_profile} /> : null}

      {!loading && !hasMatch ? (
        <section className="mx-auto mt-6 w-full max-w-5xl rounded-xl border border-cbs-columbia bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-cbs-ink">No match yet</h2>
          <p className="mt-2 text-sm text-slate-700">The Dean of Dating is still finalizing this week’s pairings. Keep your profile complete and check back soon.</p>
        </section>
      ) : null}

      {!loading && hasMatch ? (
        <section className="mx-auto mt-6 w-full max-w-5xl rounded-xl border border-cbs-columbia bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-cbs-ink">The Dean of Dating’s take</h2>
          <p className="mt-3 text-sm leading-6 text-slate-700">{overallCopy}</p>

          <h3 className="mt-5 text-sm font-semibold text-cbs-ink">Strengths</h3>
          <ul className="mt-2 space-y-2">
            {pros.map((line) => (
              <li key={line} className="text-sm text-slate-700">• {line}</li>
            ))}
          </ul>

          <h3 className="mt-5 text-sm font-semibold text-cbs-ink">Considerations</h3>
          <ul className="mt-2 space-y-2">
            {cons.map((line) => (
              <li key={line} className="text-sm text-slate-700">• {line}</li>
            ))}
          </ul>
        </section>
      ) : !loading ? (
        <section className="mx-auto mt-6 w-full max-w-5xl rounded-xl border border-cbs-columbia bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-cbs-ink">What to do next</h2>
          <p className="mt-2 text-sm text-slate-700">No action needed right now. You’ll be automatically reconsidered in the next weekly matching cycle.</p>
        </section>
      ) : null}

      {!loading && hasMatch && payload?.feedback?.eligible && !feedbackSubmitted && (
        <section className="mx-auto mt-6 w-full max-w-5xl rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-semibold text-cbs-ink">Quick feedback</h3>
          <p className="mt-1 text-sm text-cbs-slate">Internal only. This helps improve matching. Not shared with your match.</p>
          <div className="mt-4 space-y-3">
            <label className="text-sm text-slate-700">How excited are you to meet?</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  onClick={() => setCoffeeIntent(n)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                    coffeeIntent === n
                      ? "border-cbs-navy bg-cbs-navy text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            {payload.feedback.due_met_question && (
              <>
                <label className="text-sm text-slate-700">Did you message them?</label>
                <div className="flex gap-2">
                  {(["no", "yes"] as const).map((v) => (
                    <button
                      key={v}
                      onClick={() => setMet(v)}
                      className={`flex-1 rounded-lg border px-3 py-2 text-sm font-semibold uppercase transition-colors ${
                        met === v
                          ? "border-cbs-navy bg-cbs-navy text-white"
                          : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </>
            )}
            <button className="rounded-lg bg-cbs-navy px-4 py-2 text-sm font-semibold text-white hover:opacity-95" onClick={submitFeedback}>Submit feedback</button>
          </div>
        </section>
      )}

      {!loading && hasMatch && payload?.feedback?.eligible && feedbackSubmitted && (
        <section className="mx-auto mt-6 w-full max-w-5xl rounded-xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
          <h3 className="text-base font-semibold text-emerald-800">Feedback received</h3>
          <p className="mt-1 text-sm text-emerald-700">The Dean of Dating logged your notes for this match.</p>
        </section>
      )}

      {notice && <p className="mt-4 text-sm text-emerald-700">{notice}</p>}
    </div>
  );
}

export default function MatchPage() {
  return (
    <RequireAuth requireVerified requireCompletedSurvey requireCompleteProfile>
      <MatchInner />
    </RequireAuth>
  );
}
