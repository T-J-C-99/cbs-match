"use client";

import { useEffect, useState } from "react";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";

type Tenant = {
  slug: string;
  name: string;
  email_domains?: string[];
  theme?: Record<string, unknown>;
  timezone?: string;
  disabled_at?: string | null;
};

export default function AdminTenantsPage() {
  const { fetchAdmin, refreshTenants } = useAdminPortal();
  const [rows, setRows] = useState<Tenant[]>([]);
  const [error, setError] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [form, setForm] = useState({ slug: "", name: "", domains: "", themeJson: "{}", timezone: "America/New_York" });

  const load = async () => {
    setError("");
    const res = await fetchAdmin("/api/admin/tenants", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Failed to load tenants");
    setRows(Array.isArray(data.tenants) ? data.tenants : []);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async () => {
    setSaving(true);
    setError("");
    let theme: Record<string, unknown> = {};
    try {
      theme = JSON.parse(form.themeJson || "{}");
    } catch {
      setSaving(false);
      return setError("Theme must be valid JSON");
    }
    const payload = {
      slug: form.slug.trim().toLowerCase(),
      name: form.name.trim(),
      email_domains: form.domains.split(",").map((d) => d.trim().toLowerCase()).filter(Boolean),
      theme,
      timezone: form.timezone.trim() || "America/New_York",
    };
    const res = await fetchAdmin("/api/admin/tenants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    setSaving(false);
    if (!res.ok) return setError(data.detail || "Failed to save tenant");
    await load();
    await refreshTenants();
  };

  const disableTenant = async (slug: string) => {
    if (!confirm(`Disable tenant ${slug}?`)) return;
    const res = await fetchAdmin(`/api/admin/tenants/${encodeURIComponent(slug)}/disable`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.detail || "Disable failed");
    await load();
    await refreshTenants();
  };

  const syncFromShared = async () => {
    setSyncing(true);
    setError("");
    const res = await fetchAdmin("/api/admin/tenants/resync-from-shared", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    setSyncing(false);
    if (!res.ok) return setError(data.detail || "Tenant sync failed");
    await load();
    await refreshTenants();
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Tenants</h1>
        <button className="rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={syncFromShared} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync from shared config"}
        </button>
      </div>
      {error ? <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}

      <div className="mt-4 grid grid-cols-1 gap-2 rounded border border-slate-200 bg-white p-3 md:grid-cols-2">
        <input className="rounded border px-2 py-1.5" placeholder="slug" value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} />
        <input className="rounded border px-2 py-1.5" placeholder="name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        <input className="rounded border px-2 py-1.5 md:col-span-2" placeholder="domains comma-separated" value={form.domains} onChange={(e) => setForm((f) => ({ ...f, domains: e.target.value }))} />
        <input className="rounded border px-2 py-1.5" placeholder="timezone" value={form.timezone} onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))} />
        <button className="rounded bg-black px-3 py-1.5 text-sm text-white" onClick={submit} disabled={saving}>{saving ? "Saving..." : "Create / Update"}</button>
        <textarea className="rounded border px-2 py-1.5 font-mono text-xs md:col-span-2" rows={5} placeholder="theme JSON" value={form.themeJson} onChange={(e) => setForm((f) => ({ ...f, themeJson: e.target.value }))} />
      </div>

      <div className="mt-4 overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left">
            <tr><th className="p-2">Slug</th><th className="p-2">Name</th><th className="p-2">Domains</th><th className="p-2">Timezone</th><th className="p-2">Status</th><th className="p-2" /></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.slug} className="border-t">
                <td className="p-2">{r.slug}</td>
                <td className="p-2">{r.name}</td>
                <td className="p-2">{(r.email_domains || []).join(", ")}</td>
                <td className="p-2">{r.timezone || "-"}</td>
                <td className="p-2">{r.disabled_at ? "Disabled" : "Active"}</td>
                <td className="p-2 text-right">
                  {!r.disabled_at ? <button className="rounded border px-2 py-1" onClick={() => disableTenant(r.slug)}>Disable</button> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
