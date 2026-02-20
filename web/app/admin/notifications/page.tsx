"use client";

import { useEffect, useMemo, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";
import { getTenantScopeParam } from "@/lib/admin-tenant-scope";

type OutboxRow = Record<string, any>;

export default function AdminNotificationsPage() {
  const { tenantSlug, fetchAdmin } = useAdminPortal();
  const [rows, setRows] = useState<OutboxRow[]>([]);
  const [selected, setSelected] = useState<OutboxRow | null>(null);
  const [status, setStatus] = useState("pending");
  const [channel, setChannel] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [diag, setDiag] = useState<any>(null);
  const tenantScope = getTenantScopeParam(tenantSlug);

  const filters = useMemo(() => {
    const qs = new URLSearchParams({ status, limit: "25", offset: String(offset) });
    if (tenantScope) qs.set("tenant_slug", tenantScope);
    if (channel) qs.set("notification_type", channel);
    if (dateFrom) qs.set("date_from", dateFrom);
    if (dateTo) qs.set("date_to", dateTo);
    return qs;
  }, [status, tenantScope, channel, dateFrom, dateTo, offset]);

  const load = async () => {
    setLoading(true);
    setError("");
    const [res, dRes] = await Promise.all([
      fetchAdmin(`/api/admin/notifications/outbox-v2?${filters.toString()}`),
      fetchAdmin(`/api/admin/diagnostics`),
    ]);
    const data = await res.json().catch(() => ({}));
    const d = await dRes.json().catch(() => ({}));
    setLoading(false);
    if (!res.ok) return setError(data.detail || "Failed to load outbox");
    setRows(Array.isArray(data.rows) ? data.rows : []);
    setCount(Number(data.count || 0));
    if (dRes.ok) setDiag(d);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const processOutbox = async () => {
    if (!confirm("Process pending notifications for current scope?")) return;
    setMessage("");
    const res = await fetchAdmin(`/api/admin/notifications/process?limit=100${tenantScope ? `&tenant_slug=${encodeURIComponent(tenantScope)}` : ""}`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Process failed");
    setMessage(`Processed notifications. ${JSON.stringify(data)}`);
    await load();
  };

  const retry = async (id: string) => {
    const res = await fetchAdmin(`/api/admin/notifications/retry/${encodeURIComponent(id)}`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Retry failed");
    setMessage("Notification reset to pending.");
    await load();
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Notifications outbox v2</h1>
      {error ? <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}
      {message ? <p className="mt-3 rounded bg-emerald-50 p-2 text-sm text-emerald-700">{message}</p> : null}

      <div className="mt-3 rounded border bg-white p-3 text-sm">Pending by tenant: {(diag?.by_tenant || []).map((t:any)=>`${t.tenant_slug}:${t.notifications_pending}`).join(" · ") || "n/a"}</div>

      <div className="mt-3 grid grid-cols-1 gap-2 rounded border bg-white p-3 md:grid-cols-6">
        <select className="rounded border px-2 py-1.5" value={status} onChange={(e)=>{setOffset(0);setStatus(e.target.value);}}><option value="pending">pending</option><option value="sent">sent</option><option value="failed">failed</option></select>
        <input className="rounded border px-2 py-1.5" placeholder="channel/type" value={channel} onChange={(e)=>setChannel(e.target.value)} />
        <input type="date" className="rounded border px-2 py-1.5" value={dateFrom} onChange={(e)=>setDateFrom(e.target.value)} />
        <input type="date" className="rounded border px-2 py-1.5" value={dateTo} onChange={(e)=>setDateTo(e.target.value)} />
        <button className="rounded border px-3 py-1.5" onClick={()=>{setOffset(0);load();}}>Apply</button>
        <button className="rounded bg-black px-3 py-1.5 text-white" onClick={processOutbox}>Process scope</button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
        <div className="overflow-x-auto rounded border bg-white">
          <table className="min-w-full text-sm"><thead className="bg-slate-50 text-left"><tr><th className="p-2">ID</th><th className="p-2">Status</th><th className="p-2">Channel</th><th className="p-2">To</th><th className="p-2">Created</th><th className="p-2">Attempts</th><th className="p-2" /></tr></thead><tbody>
            {rows.map((r)=><tr key={r.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={()=>setSelected(r)}><td className="p-2">{r.id}</td><td className="p-2">{r.status||"-"}</td><td className="p-2">{r.notification_type||r.channel||"-"}</td><td className="p-2">{r.to_address||r.user_id||"-"}</td><td className="p-2">{r.created_at||"-"}</td><td className="p-2">{r.attempts ?? 0}</td><td className="p-2">{r.status==="failed"?<button className="rounded border px-2 py-1" onClick={(e)=>{e.stopPropagation();retry(r.id);}}>Retry</button>:null}</td></tr>)}
          </tbody></table>
          {!loading && rows.length===0 ? <p className="p-3 text-sm text-slate-500">No rows for this scope. If unexpected, run matching and process notifications.</p>:null}
        </div>
        <div className="rounded border bg-white p-3 text-sm"><h2 className="font-semibold">Detail</h2>{!selected?<p className="mt-2 text-slate-500">Select a row to inspect payload and last error.</p>:<pre className="mt-2 max-h-[440px] overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">{JSON.stringify(selected,null,2)}</pre>}</div>
      </div>
      <div className="mt-3 flex items-center gap-2 text-sm"><span>Showing {rows.length} of {count}</span><button className="rounded border px-2 py-1" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-25))}>Prev</button><button className="rounded border px-2 py-1" disabled={offset+25>=count} onClick={()=>setOffset(offset+25)}>Next</button></div>
    </div>
  );
}
