"use client";

import { useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";
import { getTenantScopeParam } from "@/lib/admin-tenant-scope";

const pct = (v: number | undefined) => typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—";

export default function AdminMetricsPage() {
  const { tenantSlug } = useAdminPortal();
  const tenantScope = getTenantScopeParam(tenantSlug);
  const today = new Date().toISOString().slice(0, 10);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [weekStart, setWeekStart] = useState(today);
  const [summary, setSummary] = useState<any>(null);
  const [funnel, setFunnel] = useState<any>(null);
  const [diag, setDiag] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    const s = await fetch(`/api/admin/metrics/summary?${new URLSearchParams({ date_from: dateFrom, date_to: dateTo, ...(tenantScope ? { tenant_slug: tenantScope } : {}) })}`);
    const f = await fetch(`/api/admin/metrics/funnel?${new URLSearchParams({ week_start: weekStart, ...(tenantScope ? { tenant_slug: tenantScope } : {}) })}`);
    const d = await fetch(`/api/admin/diagnostics`);
    const sj = await s.json().catch(() => ({}));
    const fj = await f.json().catch(() => ({}));
    const dj = await d.json().catch(() => ({}));
    if (!s.ok) return setError(sj.detail || "Could not load summary metrics");
    if (!f.ok) return setError(fj.detail || "Could not load weekly funnel");
    setSummary(sj); setFunnel(fj); if (d.ok) setDiag(dj);
  };

  const exportTable = () => {
    const counts = funnel?.counts || {};
    const rows = Object.entries(counts).map(([k, v]) => `${k},${v}`);
    const blob = new Blob([["metric,value", ...rows].join("\n")], { type: "text/csv" });
    const u = URL.createObjectURL(blob); const a=document.createElement("a"); a.href=u; a.download=`weekly-funnel-${weekStart}.csv`; a.click(); URL.revokeObjectURL(u);
  };

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Metrics dashboard</h1>
      {error && <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="mt-4 grid grid-cols-1 gap-2 rounded border bg-white p-3 md:grid-cols-5">
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded border px-2 py-1.5 text-sm" />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded border px-2 py-1.5 text-sm" />
        <input type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} className="rounded border px-2 py-1.5 text-sm" />
        <div className="rounded border bg-slate-50 px-2 py-1.5 text-sm">Tenant: {tenantScope || "All"}</div>
        <button className="rounded bg-black px-3 py-1.5 text-sm text-white" onClick={load}>Load</button>
      </div>

      <section className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
        {Object.entries(summary?.totals || {}).map(([k, v]) => <div key={k} className="rounded border bg-white p-3 text-sm"><div className="text-xs text-slate-500">{k}</div><div className="text-xl font-semibold">{String(v)}</div></div>)}
      </section>

      <section className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded border bg-white p-3"><h2 className="font-semibold">Weekly funnel ({weekStart})</h2><div className="mt-2 space-y-1 text-sm">{Object.entries(funnel?.counts || {}).map(([k,v])=><div key={k} className="flex justify-between border-b py-1"><span>{k}</span><b>{String(v)}</b></div>)}</div><div className="mt-2 grid grid-cols-2 gap-2 text-xs">{Object.entries(funnel?.rates || {}).map(([k,v])=><div key={k} className="rounded border bg-slate-50 p-1"><div>{k}</div><b>{pct(v as number)}</b></div>)}</div><button className="mt-3 rounded border px-2 py-1 text-xs" onClick={exportTable}>Export CSV</button></div>
        <div className="rounded border bg-white p-3"><h2 className="font-semibold">Tenant comparison snapshot</h2><div className="mt-2 space-y-1 text-sm">{(diag?.by_tenant || []).map((t:any)=><div key={t.tenant_slug} className="flex justify-between border-b py-1"><span>{t.tenant_slug}</span><span>users {t.users_total} · eligible {t.eligible_users} · assign {t.assignments_current_week}</span></div>)}</div></div>
      </section>
    </div>
  );
}
