"use client";

import { useEffect, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";
import { getTenantScopeParam } from "@/lib/admin-tenant-scope";

const KPI_PERCENT_KEYS = new Set(["onboarding_completion_pct", "match_eligible_pct", "accept_rate"]);

export default function AdminPage() {
  const { tenantSlug } = useAdminPortal();
  const [data, setData] = useState<any>(null);
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [coverage, setCoverage] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [seedLoading, setSeedLoading] = useState(false);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tenantScope = getTenantScopeParam(tenantSlug);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (tenantScope) params.set("tenant_slug", tenantScope);
    const res = await fetch(`/api/admin/dashboard${params.toString() ? `?${params.toString()}` : ""}`);
    const payload = await res.json().catch(() => ({}));
    setLoading(false);
    if (!res.ok) {
      setError(payload?.detail || "Failed to load dashboard");
      return;
    }
    setData(payload);

    const [dRes, cRes] = await Promise.all([
      fetch(`/api/admin/diagnostics`, { cache: "no-store" }),
      fetch(`/api/admin/diagnostics/tenant-coverage`, { cache: "no-store" }),
    ]);
    const dPayload = await dRes.json().catch(() => ({}));
    const cPayload = await cRes.json().catch(() => ({}));
    if (dRes.ok) setDiagnostics(dPayload);
    if (cRes.ok) setCoverage(cPayload);
  };

  useEffect(() => {
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantScope]);

  const runSeedAllTenants = async () => {
    if (!confirm("Seed all tenants with reset=true and 60 users per tenant? This recreates tenant-scoped seeded data.")) return;
    setSeedLoading(true);
    setError(null);
    const res = await fetch("/api/admin/seed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ all_tenants: true, n_users_per_tenant: 60, reset: true, include_qa_login: true }),
    });
    const payload = await res.json().catch(() => ({}));
    setSeedLoading(false);
    if (!res.ok) {
      setError(payload?.detail || "Seed all tenants failed");
      return;
    }
    await loadDashboard();
  };

  const runBackfillExistingUsers = async () => {
    if (!confirm("Backfill completed survey sessions/traits for all existing users without current survey traits?")) return;
    setBackfillLoading(true);
    setError(null);
    const res = await fetch("/api/admin/seed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ all_tenants: true, backfill_existing_users: true, force_reseed: false, include_qa_login: false }),
    });
    const payload = await res.json().catch(() => ({}));
    setBackfillLoading(false);
    if (!res.ok) {
      setError(payload?.detail || "Backfill existing users failed");
      return;
    }
    await loadDashboard();
  };

  const byTenant: Array<any> = diagnostics?.by_tenant || [];
  const coverageByTenant: Array<any> = coverage?.by_tenant || [];
  const totals = byTenant.reduce(
    (acc, row) => {
      acc.users += Number(row.users_total || 0);
      acc.eligible += Number(row.eligible_users || 0);
      acc.assignments += Number(row.assignments_current_week || 0);
      acc.pending += Number(row.notifications_pending || 0);
      acc.openReports += Number(row.open_safety_reports || 0);
      return acc;
    },
    { users: 0, eligible: 0, assignments: 0, pending: 0, openReports: 0 }
  );
  const maxTenantUsers = byTenant.reduce((m: number, row: any) => Math.max(m, Number(row.users_total || 0)), 0);
  const showAnomaly =
    byTenant.length > 1 &&
    ((totals.users > 0 && totals.users === maxTenantUsers) || byTenant.some((row: any) => Number(row.users_total || 0) === 0));

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-600">Tenant-aware admin KPIs and recent activity.</p>
        </div>
        <button className="rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={loadDashboard} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
        <button className="rounded bg-black px-3 py-1.5 text-sm text-white" onClick={runSeedAllTenants} disabled={seedLoading}>
          {seedLoading ? "Seeding..." : "Seed all tenants"}
        </button>
        <button className="rounded border border-slate-400 px-3 py-1.5 text-sm" onClick={runBackfillExistingUsers} disabled={backfillLoading}>
          {backfillLoading ? "Backfilling..." : "Backfill existing users survey"}
        </button>
      </div>

      {error ? <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
        {Object.entries(data?.kpis || {}).map(([key, value]) => (
          <div key={key} className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-xs uppercase text-slate-500">{key}</div>
            <div className="mt-1 text-xl font-semibold text-slate-900">
              {typeof value === "number"
                ? KPI_PERCENT_KEYS.has(key)
                  ? `${(key === "accept_rate" ? value * 100 : value).toFixed(1)}%`
                  : value.toLocaleString()
                : String(value)}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 text-sm font-semibold">Admin health diagnostics</div>
        {!diagnostics ? (
          <p className="text-sm text-slate-500">Diagnostics unavailable.</p>
        ) : (
          <>
            <div className="text-xs text-slate-600">
              Week: {diagnostics.week_start_date} · Tenants: {diagnostics.tenants_count}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
              <div className="rounded border border-slate-200 p-2">Users total: <b>{totals.users}</b></div>
              <div className="rounded border border-slate-200 p-2">Eligible total: <b>{totals.eligible}</b></div>
              <div className="rounded border border-slate-200 p-2">Assignments: <b>{totals.assignments}</b></div>
              <div className="rounded border border-slate-200 p-2">Pending outbox: <b>{totals.pending}</b></div>
              <div className="rounded border border-slate-200 p-2">Open reports: <b>{totals.openReports}</b></div>
            </div>
            {showAnomaly ? (
              <div className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
                Diagnostic warning: multi-tenant totals look suspicious (one tenant dominates or some tenants are zero). Run “Seed all tenants”, then refresh diagnostics.
              </div>
            ) : null}
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
              {(diagnostics.by_tenant || []).map((t: any) => (
                <div key={t.tenant_slug} className="rounded border border-slate-200 p-2 text-xs">
                  <div className="font-semibold">{t.tenant_name} ({t.tenant_slug})</div>
                  <div>users: {t.users_total}</div>
                  <div>assignments: {t.assignments_current_week}</div>
                  <div>pending outbox: {t.notifications_pending}</div>
                  <div>open reports: {t.open_safety_reports}</div>
                </div>
              ))}
            </div>
            {coverageByTenant.length > 0 ? (
              <div className="mt-3">
                <div className="mb-1 text-xs font-semibold">Tenant coverage checklist</div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-xs">
                    <thead>
                      <tr className="border-b">
                        <th className="py-1 pr-3">Tenant</th>
                        <th className="py-1 pr-3">Users</th>
                        <th className="py-1 pr-3">Completed survey</th>
                        <th className="py-1 pr-3">Traits</th>
                        <th className="py-1 pr-3">Week assignments</th>
                        <th className="py-1 pr-3">Outbox pending</th>
                        <th className="py-1">Open reports</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coverageByTenant.map((row: any) => (
                        <tr key={row.tenant_slug} className="border-b last:border-b-0">
                          <td className="py-1 pr-3">{row.tenant_slug}</td>
                          <td className="py-1 pr-3">{row.users_total}</td>
                          <td className="py-1 pr-3">{row.users_with_completed_survey}</td>
                          <td className="py-1 pr-3">{row.users_with_traits}</td>
                          <td className="py-1 pr-3">{row.weekly_assignment_rows}</td>
                          <td className="py-1 pr-3">{row.outbox_pending}</td>
                          <td className="py-1">{row.open_reports}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h2 className="text-sm font-semibold">Recent admin audit</h2>
          <pre className="mt-2 max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(data?.recent_activity?.audit || [], null, 2)}</pre>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h2 className="text-sm font-semibold">Open safety reports</h2>
          <pre className="mt-2 max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(data?.recent_activity?.open_reports || [], null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
