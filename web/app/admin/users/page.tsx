"use client";

import { useEffect, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";
import { getTenantScopeParam } from "@/lib/admin-tenant-scope";

type UserRow = {
  id: string;
  email?: string;
  username?: string;
  tenant_slug?: string;
  onboarding_status?: string;
  pause_matches?: boolean;
  display_name?: string;
  created_at?: string;
  last_login_at?: string;
  is_match_eligible?: boolean;
  blocks_count?: number;
  last_match_week?: string;
  traits_version?: number;
};

export default function AdminUsersPage() {
  const { tenantSlug, tenants, fetchAdmin } = useAdminPortal();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [tenantFilter, setTenantFilter] = useState("");
  const [status, setStatus] = useState("");
  const [eligibleOnly, setEligibleOnly] = useState(false);
  const [pausedOnly, setPausedOnly] = useState(false);
  const [limit, setLimit] = useState("200");
  const [selected, setSelected] = useState<UserRow | null>(null);
  const tenantScope = getTenantScopeParam(tenantFilter || tenantSlug);

  const load = async (nextOffset = offset) => {
    setLoading(true);
    setError("");
    const qs = new URLSearchParams({ limit: limit || "200", offset: String(nextOffset || 0) });
    if (tenantScope) qs.set("tenant_slug", tenantScope);
    if (status) qs.set("onboarding_status", status);
    if (search.trim()) qs.set("search", search.trim());
    if (eligibleOnly) qs.set("eligible_only", "true");
    if (pausedOnly) qs.set("paused_only", "true");
    const res = await fetchAdmin(`/api/admin/users?${qs.toString()}`);
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (!res.ok) return setError(data.detail || "Failed to load users");
    setRows(Array.isArray(data.users) ? data.users : []);
    setCount(Number(data.count || 0));
    setOffset(Number(data.offset || 0));
  };

  useEffect(() => {
    setTenantFilter(tenantSlug || "");
    setOffset(0);
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantSlug]);

  const pauseUser = async (userId: string, nextPause: boolean) => {
    const res = await fetchAdmin(`/api/admin/users/${encodeURIComponent(userId)}/pause?pause_matches=${nextPause ? "true" : "false"}`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Pause action failed");
    await load();
  };

  const deleteUser = async (userId: string) => {
    if (!confirm("Delete/anonymize this user?")) return;
    const res = await fetchAdmin(`/api/admin/users/${encodeURIComponent(userId)}/delete`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Delete failed");
    await load();
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Users</h1>
      {error ? <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}

      <div className="mt-4 flex flex-wrap items-center gap-2 rounded border border-slate-200 bg-white p-3 text-sm">
        <select className="rounded border px-2 py-1.5" value={tenantFilter} onChange={(e) => setTenantFilter(e.target.value)}>
          <option value="">All tenants</option>
          {tenants.map((t) => (
            <option key={t.slug} value={t.slug}>{t.name} ({t.slug})</option>
          ))}
        </select>
        <input className="rounded border px-2 py-1.5" placeholder="search email/username/id" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="rounded border px-2 py-1.5" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">all onboarding</option>
          <option value="not_started">not_started</option>
          <option value="in_progress">in_progress</option>
          <option value="complete">complete</option>
        </select>
        <label className="inline-flex items-center gap-2"><input type="checkbox" checked={eligibleOnly} onChange={(e) => setEligibleOnly(e.target.checked)} />Eligible only</label>
        <label className="inline-flex items-center gap-2"><input type="checkbox" checked={pausedOnly} onChange={(e) => setPausedOnly(e.target.checked)} />Paused only</label>
        <input className="w-20 rounded border px-2 py-1.5" value={limit} onChange={(e) => setLimit(e.target.value)} />
        <button className="rounded border px-3 py-1.5" onClick={() => load(0)} disabled={loading}>{loading ? "Loading..." : "Apply"}</button>
        <span className="text-slate-600">Total: {count}</span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left">
            <tr><th className="p-2">Email</th><th className="p-2">Username</th><th className="p-2">Tenant</th><th className="p-2">Onboarding</th><th className="p-2">Eligible</th><th className="p-2">Paused</th><th className="p-2" /></tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={() => setSelected(u)}>
                <td className="p-2">{u.email || "-"}</td>
                <td className="p-2">{u.username || "-"}</td>
                <td className="p-2">{u.tenant_slug || "-"}</td>
                <td className="p-2">{u.onboarding_status || "-"}</td>
                <td className="p-2">{u.is_match_eligible ? "Yes" : "No"}</td>
                <td className="p-2">{u.pause_matches ? "Yes" : "No"}</td>
                <td className="p-2 text-right space-x-2">
                  <button className="rounded border px-2 py-1" onClick={() => pauseUser(u.id, !u.pause_matches)}>{u.pause_matches ? "Unpause" : "Pause"}</button>
                  <button className="rounded border px-2 py-1" onClick={() => deleteUser(u.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rounded border border-slate-200 bg-white p-3 text-sm">
        <div className="font-semibold">User detail</div>
        {!selected ? <p className="mt-2 text-slate-500">Select a user to inspect details.</p> : (
          <div className="mt-2 space-y-1 text-xs">
            <div><span className="font-medium">ID:</span> {selected.id}</div>
            <div><span className="font-medium">Name:</span> {selected.display_name || "-"}</div>
            <div><span className="font-medium">Tenant:</span> {selected.tenant_slug || "-"}</div>
            <div><span className="font-medium">Onboarding:</span> {selected.onboarding_status || "-"}</div>
            <div><span className="font-medium">Last login:</span> {selected.last_login_at || "-"}</div>
            <div><span className="font-medium">Created:</span> {selected.created_at || "-"}</div>
            <div><span className="font-medium">Traits version:</span> {selected.traits_version ?? "-"}</div>
            <div><span className="font-medium">Last match week:</span> {selected.last_match_week || "-"}</div>
            <div><span className="font-medium">Blocks count:</span> {selected.blocks_count ?? 0}</div>
          </div>
        )}
      </div>
      </div>

      <div className="mt-3 flex items-center gap-2 text-sm">
        <button className="rounded border px-2 py-1" disabled={offset <= 0 || loading} onClick={() => load(Math.max(0, offset - Number(limit || 200)))}>Prev</button>
        <button className="rounded border px-2 py-1" disabled={offset + Number(limit || 200) >= count || loading} onClick={() => load(offset + Number(limit || 200))}>Next</button>
        <span className="text-slate-600">Showing {rows.length} / {count} (offset {offset})</span>
      </div>
    </div>
  );
}
