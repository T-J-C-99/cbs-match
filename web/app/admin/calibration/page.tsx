"use client";

import { useEffect, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";

export default function AdminCalibrationPage() {
  const { fetchAdmin } = useAdminPortal();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const load = async () => {
    setError(null);
    const res = await fetchAdmin(`/api/admin/calibration/current-week`);
    const json = await res.json().catch(() => ({}));
    if (!res.ok) return setError(json.detail || "Failed to load calibration report");
    setData(json);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const p = data?.pair_score_distribution?.percentiles || {};
  const a = data?.assigned_distribution?.percentiles || {};

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-semibold">Calibration report</h1>
      <button className="mt-3 rounded bg-black px-3 py-1.5 text-sm text-white" onClick={load}>Reload</button>
      {error && <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
        <div className="rounded border bg-white p-3 text-sm"><div className="text-xs text-slate-500">eligible_users</div><div className="text-xl font-semibold">{data?.eligible_users ?? 0}</div></div>
        <div className="rounded border bg-white p-3 text-sm"><div className="text-xs text-slate-500">candidate_pair_count</div><div className="text-xl font-semibold">{data?.candidate_pair_count ?? 0}</div></div>
        <div className="rounded border bg-white p-3 text-sm"><div className="text-xs text-slate-500">assigned_rows</div><div className="text-xl font-semibold">{data?.assignment_counts?.total_assignments ?? 0}</div></div>
        <div className="rounded border bg-white p-3 text-sm"><div className="text-xs text-slate-500">no_match_rate</div><div className="text-xl font-semibold">{(((data?.assignment_counts?.no_match_rate ?? 0) as number) * 100).toFixed(1)}%</div></div>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded border bg-white p-3 text-sm"><h2 className="font-semibold">Pair score percentiles</h2><div className="mt-2 space-y-1">{Object.entries(p).map(([k,v])=><div key={k} className="flex justify-between"><span>{k}</span><b>{String(v ?? "—")}</b></div>)}</div></div>
        <div className="rounded border bg-white p-3 text-sm"><h2 className="font-semibold">Assigned score percentiles</h2><div className="mt-2 space-y-1">{Object.entries(a).map(([k,v])=><div key={k} className="flex justify-between"><span>{k}</span><b>{String(v ?? "—")}</b></div>)}</div></div>
      </div>
      <button className="mt-4 rounded border px-2 py-1 text-xs" onClick={()=>setShowRaw((v)=>!v)}>{showRaw?"Hide":"Show"} raw JSON</button>
      {showRaw && data ? <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(data, null, 2)}</pre> : null}
    </div>
  );
}
