"use client";

import { useEffect, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";
import { getTenantScopeParam } from "@/lib/admin-tenant-scope";

type RunResult = Record<string, any>;

function isoWeekStart(date = new Date()) {
  const d = new Date(date);
  const day = d.getDay();
  const diffToMonday = (day + 6) % 7;
  d.setDate(d.getDate() - diffToMonday);
  return d.toISOString().slice(0, 10);
}

function toCsv(rows: Array<Record<string, unknown>>) {
  if (!rows.length) return "";
  const keys = Object.keys(rows[0]);
  const esc = (v: unknown) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  return [keys.join(","), ...rows.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
}

export default function AdminMatchingPage() {
  const { tenantSlug, fetchAdmin } = useAdminPortal();
  const tenantScope = getTenantScopeParam(tenantSlug);
  const [weekStart, setWeekStart] = useState(isoWeekStart());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [diag, setDiag] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);

  const loadStatus = async () => {
    setError("");
    const [dRes, sRes] = await Promise.all([
      fetchAdmin("/api/admin/diagnostics"),
      fetchAdmin(`/api/admin/week/${weekStart}${tenantScope ? `?tenant_slug=${encodeURIComponent(tenantScope)}` : ""}`),
    ]);
    const d = await dRes.json().catch(() => ({}));
    const s = await sRes.json().catch(() => ({}));
    if (!dRes.ok) return setError(d.detail || "Failed to load diagnostics");
    if (!sRes.ok) return setError(s.detail || "Failed to load week summary");
    setDiag(d);
    setSummary(s);
  };

  useEffect(() => {
    loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantScope, weekStart]);

  const run = async (opts: { force: boolean; allTenants?: boolean }) => {
    if (opts.force && !confirm(opts.allTenants ? "Force rerun all tenants? Existing week rows/events/feedback/outbox rows will be deleted and recreated." : "Force rerun selected tenant? Existing week rows/events/feedback/outbox rows will be deleted and recreated.")) return;
    setLoading(true);
    setError("");
    setMessage("");
    const qs = new URLSearchParams({ force: opts.force ? "true" : "false" });
    if (opts.allTenants) qs.set("all_tenants", "true");
    if (tenantScope) qs.set("tenant_slug", tenantScope);
    const res = await fetchAdmin(`/api/admin/run-weekly?${qs.toString()}`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (!res.ok) return setError(data.detail || "Weekly run failed");
    setLastRun(data);
    if (typeof data?.week_start_date === "string" && data.week_start_date) {
      setWeekStart(data.week_start_date);
    }
    setMessage("Weekly matching run completed.");
    await loadStatus();
  };

  const downloadAssignments = () => {
    const rows = Array.isArray(summary?.assignments) ? summary.assignments : [];
    if (!rows.length) return setError("No assignments found for CSV export.");
    const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `assignments-${tenantScope || "all"}-${weekStart}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Matching operations</h1>
      <p className="mt-1 text-sm text-slate-600">Run weekly matching, inspect per-tenant status, and export weekly assignment rows.</p>
      {error ? <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}
      {message ? <p className="mt-3 rounded bg-emerald-50 p-2 text-sm text-emerald-700">{message}</p> : null}

      <div className="mt-4 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-3 md:grid-cols-[1fr_auto_auto_auto]">
        <label className="text-sm">Week start (Mon)<input type="date" className="ml-2 rounded border px-2 py-1" value={weekStart} onChange={(e) => setWeekStart(isoWeekStart(new Date(e.target.value)))} /></label>
        <button className="rounded border px-3 py-1.5 text-sm" onClick={() => run({ force: false })} disabled={loading}>Run weekly</button>
        <button className="rounded border px-3 py-1.5 text-sm" onClick={() => run({ force: true })} disabled={loading || !tenantScope}>Force rerun tenant</button>
        <button className="rounded bg-black px-3 py-1.5 text-sm text-white" onClick={() => run({ force: true, allTenants: true })} disabled={loading}>Force rerun all</button>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Per-tenant status (current week)</h2><button className="rounded border px-2 py-1 text-xs" onClick={loadStatus}>Refresh</button></div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm"><thead className="bg-slate-50 text-left"><tr><th className="p-2">Tenant</th><th className="p-2">Users</th><th className="p-2">Eligible</th><th className="p-2">Assignments</th><th className="p-2">Pairs</th><th className="p-2">Accepts</th><th className="p-2">Feedback</th></tr></thead><tbody>
            {(diag?.by_tenant || []).map((r: any) => <tr key={r.tenant_slug} className="border-t"><td className="p-2">{r.tenant_name} ({r.tenant_slug})</td><td className="p-2">{r.users_total}</td><td className="p-2">{r.eligible_users}</td><td className="p-2">{r.assignments_current_week}</td><td className="p-2">{r.unique_pairs_current_week}</td><td className="p-2">{r.accepts_current_week}</td><td className="p-2">{r.feedback_count_current_week}</td></tr>)}
          </tbody></table>
          {!diag?.by_tenant?.length ? <p className="p-3 text-sm text-slate-500">No tenant status rows yet. Try syncing tenants and seeding data.</p> : null}
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Week summary ({tenantScope || "all tenants"})</h2><button className="rounded border px-2 py-1 text-xs" onClick={downloadAssignments}>Download assignments CSV</button></div>
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div className="rounded border p-2">Rows: <b>{summary?.total_assignments ?? 0}</b></div>
          <div className="rounded border p-2">Matched: <b>{summary?.status_counts?.matched ?? 0}</b></div>
          <div className="rounded border p-2">Accepted: <b>{summary?.event_counts?.accept ?? 0}</b></div>
          <div className="rounded border p-2">No match: <b>{summary?.status_counts?.no_match ?? 0}</b></div>
        </div>
      </div>

      {lastRun ? <pre className="mt-4 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(lastRun, null, 2)}</pre> : null}
    </div>
  );
}
