"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShellNav from "@/components/AppShellNav";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type NotificationPreferences = {
  email_enabled: boolean;
  push_enabled: boolean;
  quiet_hours_start_local: string | null;
  quiet_hours_end_local: string | null;
  timezone: string;
};

function SettingsInner() {
  const router = useRouter();
  const { user, fetchWithAuth, logout } = useAuth();

  const [pauseMatches, setPauseMatches] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pauseStatus, setPauseStatus] = useState<string>("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [blockId, setBlockId] = useState("");
  const [reportReason, setReportReason] = useState("");
  const [notifPrefs, setNotifPrefs] = useState<NotificationPreferences>({
    email_enabled: true,
    push_enabled: false,
    quiet_hours_start_local: null,
    quiet_hours_end_local: null,
    timezone: "America/New_York",
  });
  const [notifSaving, setNotifSaving] = useState(false);

  const togglePause = async () => {
    const nextValue = !pauseMatches;
    const previousValue = pauseMatches;
    setPauseMatches(nextValue);
    setSaving(true);
    setPauseStatus("Saving...");
    setError(null);
    try {
      const res = await fetchWithAuth(`${API_BASE}/users/me/preferences`, {
        method: "PUT",
        body: JSON.stringify({ pause_matches: nextValue }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not save settings");
      setPauseStatus(nextValue ? "Paused" : "Active");
      setNotice(nextValue ? "Matching paused." : "Matching resumed.");
    } catch (e) {
      setPauseMatches(previousValue);
      setPauseStatus("Could not save");
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [prefRes, notifRes] = await Promise.all([
          fetchWithAuth(`${API_BASE}/users/me/preferences`),
          fetchWithAuth(`${API_BASE}/users/me/notification-preferences`),
        ]);
        const data = await prefRes.json().catch(() => ({}));
        const notifData = await notifRes.json().catch(() => ({}));
        if (!prefRes.ok) throw new Error(data.detail || "Could not load settings");
        if (!notifRes.ok) throw new Error(notifData.detail || "Could not load notification settings");
        setPauseMatches(Boolean(data?.preferences?.pause_matches));
        const p = (notifData?.preferences || {}) as Partial<NotificationPreferences>;
        setNotifPrefs({
          email_enabled: Boolean(p.email_enabled ?? true),
          push_enabled: Boolean(p.push_enabled ?? false),
          quiet_hours_start_local: typeof p.quiet_hours_start_local === "string" ? p.quiet_hours_start_local : null,
          quiet_hours_end_local: typeof p.quiet_hours_end_local === "string" ? p.quiet_hours_end_local : null,
          timezone: typeof p.timezone === "string" && p.timezone ? p.timezone : "America/New_York",
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [fetchWithAuth]);

  const doLogout = async () => {
    await logout();
    router.replace("/landing");
  };

  const deleteAccount = async () => {
    const confirm1 = window.confirm("Delete account? This removes your public profile and match visibility.");
    if (!confirm1) return;
    const confirm2 = window.confirm("Final confirmation: this cannot be undone.");
    if (!confirm2) return;

    const res = await fetchWithAuth(`${API_BASE}/users/me/account`, { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Could not delete account");
      return;
    }
    await logout();
    router.replace("/landing");
  };

  const sendFeedback = async () => {
    setError(null);
    const msg = feedbackMessage.trim();
    if (!msg) {
      setError("Please enter feedback first.");
      return;
    }
    const res = await fetchWithAuth(`${API_BASE}/users/me/support/feedback`, {
      method: "POST",
      body: JSON.stringify({ message: msg }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Could not send feedback");
      return;
    }
    setFeedbackMessage("");
    setNotice("Thanks — feedback sent.");
  };

  const blockUser = async () => {
    setError(null);
    const id = blockId.trim();
    if (!id) {
      setError("Enter a user ID to block.");
      return;
    }
    const res = await fetchWithAuth(`${API_BASE}/safety/block`, {
      method: "POST",
      body: JSON.stringify({ blocked_user_id: id }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Could not block user");
      return;
    }
    setBlockId("");
    setNotice("User blocked.");
  };

  const reportCurrent = async () => {
    setError(null);
    const reason = reportReason.trim();
    if (!reason) {
      setError("Please enter a reason before reporting.");
      return;
    }
    const res = await fetchWithAuth(`${API_BASE}/safety/report`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail || "Could not report current match");
      return;
    }
    setNotice("Report submitted.");
  };

  const saveNotificationPrefs = async () => {
    setNotifSaving(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`${API_BASE}/users/me/notification-preferences`, {
        method: "PUT",
        body: JSON.stringify(notifPrefs),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not save notification preferences");
      const p = (data?.preferences || {}) as Partial<NotificationPreferences>;
      setNotifPrefs({
        email_enabled: Boolean(p.email_enabled ?? notifPrefs.email_enabled),
        push_enabled: Boolean(p.push_enabled ?? notifPrefs.push_enabled),
        quiet_hours_start_local: typeof p.quiet_hours_start_local === "string" ? p.quiet_hours_start_local : null,
        quiet_hours_end_local: typeof p.quiet_hours_end_local === "string" ? p.quiet_hours_end_local : null,
        timezone: typeof p.timezone === "string" && p.timezone ? p.timezone : notifPrefs.timezone,
      });
      setNotice("Notification preferences saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save notification preferences");
    } finally {
      setNotifSaving(false);
    }
  };

  return (
    <div className="cbs-page-shell">
      <AppShellNav />
      <h1 className="text-3xl font-semibold text-cbs-ink">Settings</h1>
      <p className="mt-2 text-sm text-cbs-slate">Account and participation preferences.</p>
      {loading && <p className="mt-2 text-xs text-cbs-slate">Syncing settings…</p>}

      {error && <p className="mt-4 rounded bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}
      {notice && <p className="mt-4 rounded bg-emerald-100 px-3 py-2 text-sm text-emerald-800">{notice}</p>}

      <section className={`mt-6 rounded-xl border p-6 shadow-sm ${pauseMatches ? "border-amber-300 bg-amber-50" : "border-cbs-columbia bg-white"}`}>
        <h2 className="text-base font-semibold text-cbs-ink">Weekly matching</h2>
        <button
          type="button"
          onClick={togglePause}
          disabled={saving}
          className={`mt-4 flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left ${pauseMatches ? "border-amber-300 bg-amber-100" : "border-slate-200 bg-slate-50"} ${saving ? "opacity-70" : ""}`}
        >
          <span className="text-sm font-medium text-slate-800">Pause new weekly matches</span>
          <span className={`inline-flex h-6 w-11 items-center rounded-full p-1 transition ${pauseMatches ? "bg-amber-500" : "bg-slate-300"}`}>
            <span className={`h-4 w-4 rounded-full bg-white transition ${pauseMatches ? "translate-x-5" : "translate-x-0"}`} />
          </span>
        </button>
        <p className="mt-2 text-xs text-cbs-slate">
          {pauseMatches
            ? "Paused: you will not receive new pairings until you switch this off."
            : "Active: you are eligible for upcoming weekly pairings."}
        </p>
        {!!pauseStatus && pauseStatus !== "Paused" && pauseStatus !== "Active" && (
          <p className={`mt-1 text-xs ${pauseStatus === "Could not save" ? "text-red-600" : "text-slate-500"}`}>{pauseStatus}</p>
        )}
      </section>

      <section className="mt-6 rounded-xl border border-cbs-columbia bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-cbs-ink">Notifications</h2>
        <p className="mt-2 text-sm text-slate-700">Choose how CBS Match reaches you and set optional quiet hours.</p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <span>Email notifications</span>
            <input
              type="checkbox"
              checked={notifPrefs.email_enabled}
              onChange={(e) => setNotifPrefs((p) => ({ ...p, email_enabled: e.target.checked }))}
            />
          </label>
          <label className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <span>Push notifications</span>
            <input
              type="checkbox"
              checked={notifPrefs.push_enabled}
              onChange={(e) => setNotifPrefs((p) => ({ ...p, push_enabled: e.target.checked }))}
            />
          </label>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <div className="mb-1 text-slate-600">Quiet start (optional)</div>
            <input
              type="time"
              value={notifPrefs.quiet_hours_start_local || ""}
              onChange={(e) => setNotifPrefs((p) => ({ ...p, quiet_hours_start_local: e.target.value || null }))}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 text-slate-600">Quiet end (optional)</div>
            <input
              type="time"
              value={notifPrefs.quiet_hours_end_local || ""}
              onChange={(e) => setNotifPrefs((p) => ({ ...p, quiet_hours_end_local: e.target.value || null }))}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 text-slate-600">Timezone</div>
            <input
              value={notifPrefs.timezone}
              onChange={(e) => setNotifPrefs((p) => ({ ...p, timezone: e.target.value || "America/New_York" }))}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
              placeholder="America/New_York"
            />
          </label>
        </div>

        <button
          onClick={saveNotificationPrefs}
          disabled={notifSaving}
          className="mt-3 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
        >
          {notifSaving ? "Saving..." : "Save notification settings"}
        </button>
      </section>

      <section className="mt-6 rounded-xl border border-cbs-columbia bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-cbs-ink">Feedback</h2>
        <p className="mt-2 text-sm text-slate-700">Internal only. Helps improve matching quality.</p>
        <textarea
          className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          rows={4}
          value={feedbackMessage}
          onChange={(e) => setFeedbackMessage(e.target.value)}
          placeholder="What should we improve?"
        />
        <button onClick={sendFeedback} className="mt-3 rounded-lg bg-cbs-navy px-4 py-2 text-sm font-semibold text-white">Send feedback</button>
      </section>

      <section className="mt-6 rounded-xl border border-cbs-columbia bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-cbs-ink">Safety</h2>
        <p className="mt-2 text-sm text-slate-700">Use safety tools any time you feel uncomfortable. Blocking prevents future matches with that person. Reporting alerts the CBS Match team about this week&apos;s match and helps us review issues quickly.</p>
        <div className="mt-4 space-y-3">
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={blockId}
            onChange={(e) => setBlockId(e.target.value)}
            placeholder="User ID, email, or username to block"
          />
          <button onClick={blockUser} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Block user</button>
          <p className="text-xs text-cbs-slate">When you block someone, they are excluded from your future match pool.</p>
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={reportReason}
            onChange={(e) => setReportReason(e.target.value)}
            placeholder="Reason (for example: safety, harassment, no-show)"
          />
          <button onClick={reportCurrent} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Report current match</button>
          <p className="text-xs text-cbs-slate">Reports are private and reviewed by the team. Reporting does not notify your match.</p>
        </div>
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-cbs-ink">Account</h2>
        <p className="mt-2 text-sm text-slate-700">Signed in as {user?.email || "unknown"}</p>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            onClick={doLogout}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Log out
          </button>
          <button
            onClick={deleteAccount}
            className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-100"
          >
            Delete account
          </button>
        </div>
      </section>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth requireVerified>
      <SettingsInner />
    </RequireAuth>
  );
}
