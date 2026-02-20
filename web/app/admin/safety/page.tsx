"use client";

import { useEffect, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";
import { getTenantScopeParam } from "@/lib/admin-tenant-scope";

type ReportRow = Record<string, any>;

export default function AdminSafetyPage() {
  const { tenantSlug, fetchAdmin } = useAdminPortal();
  const [rows, setRows] = useState<ReportRow[]>([]);
  const [selected, setSelected] = useState<ReportRow | null>(null);
  const [status, setStatus] = useState("open");
  const [reason, setReason] = useState("");
  const [reporter, setReporter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const tenantScope = getTenantScopeParam(tenantSlug);

  const load = async (nextOffset = offset) => {
    setLoading(true);
    setError("");
    const qs = new URLSearchParams({ limit: "25", offset: String(nextOffset), status });
    if (tenantScope) qs.set("tenant_slug", tenantScope);
    if (reason) qs.set("reason", reason);
    if (reporter) qs.set("reporter_user_id", reporter);
    if (dateFrom) qs.set("date_from", dateFrom);
    if (dateTo) qs.set("date_to", dateTo);
    const res = await fetchAdmin(`/api/admin/reports?${qs.toString()}`);
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (!res.ok) return setError(data.detail || "Failed to load reports");
    setRows(Array.isArray(data.reports) ? data.reports : []);
    setCount(Number(data.count || 0));
    setOffset(nextOffset);
  };

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantScope]);

  const resolve = async () => {
    if (!selected) return;
    if (!confirm("Resolve this safety report?")) return;
    const res = await fetchAdmin(`/api/admin/reports/${encodeURIComponent(selected.id)}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution_notes: notes }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Resolve failed");
    setSelected(data.report || null);
    await load(offset);
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Safety reports</h1>
      <p className="mt-1 text-sm text-slate-600">Filter, inspect, and resolve reports with audit-friendly notes.</p>
      {error ? <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}

      <div className="mt-3 grid grid-cols-1 gap-2 rounded border bg-white p-3 md:grid-cols-6">
        <select className="rounded border px-2 py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}><option value="open">open</option><option value="resolved">resolved</option></select>
        <input className="rounded border px-2 py-1.5 text-sm" placeholder="reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <input className="rounded border px-2 py-1.5 text-sm" placeholder="reporter user id" value={reporter} onChange={(e) => setReporter(e.target.value)} />
        <input type="date" className="rounded border px-2 py-1.5 text-sm" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="rounded border px-2 py-1.5 text-sm" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <button className="rounded border px-3 py-1.5 text-sm" onClick={() => load(0)}>Apply</button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
        <div className="overflow-x-auto rounded border border-slate-200 bg-white">
          <table className="min-w-full text-sm"><thead className="bg-slate-50 text-left"><tr><th className="p-2">ID</th><th className="p-2">Status</th><th className="p-2">Reason</th><th className="p-2">Created</th></tr></thead><tbody>
            {rows.map((r) => <tr key={r.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={() => setSelected(r)}><td className="p-2">{r.id}</td><td className="p-2">{r.status || "-"}</td><td className="p-2">{r.reason || "-"}</td><td className="p-2">{r.created_at || "-"}</td></tr>)}
          </tbody></table>
          {!loading && rows.length === 0 ? <p className="p-3 text-sm text-slate-500">No reports for this filter. If unexpected, seed data and verify tenant selection.</p> : null}
        </div>
        <div className="rounded border border-slate-200 bg-white p-3 text-sm">
          <h2 className="font-semibold">Detail</h2>
          {!selected ? <p className="mt-2 text-slate-500">Select a report to inspect and resolve.</p> : <>
            <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">{JSON.stringify(selected, null, 2)}</pre>
            <textarea className="mt-2 w-full rounded border px-2 py-1.5" rows={4} placeholder="resolution notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
            <div className="mt-2 flex gap-2"><button className="rounded bg-black px-3 py-1.5 text-white" onClick={resolve}>Resolve report</button><button className="rounded border px-3 py-1.5" onClick={() => {const blob=new Blob([JSON.stringify(selected,null,2)],{type:'application/json'});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=`report-${selected.id}.json`;a.click();URL.revokeObjectURL(u);}}>Export JSON</button></div>
          </>}
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 text-sm"><span>Showing {rows.length} of {count}</span><button className="rounded border px-2 py-1" disabled={offset===0} onClick={()=>load(Math.max(0,offset-25))}>Prev</button><button className="rounded border px-2 py-1" disabled={offset+25>=count} onClick={()=>load(offset+25)}>Next</button></div>
    </div>
  );
}
