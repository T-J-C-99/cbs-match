"use client";

import { useRouter } from "next/navigation";
import { allTenants, clearTenantClientContext, setTenantClientContext } from "@/lib/tenant";

export default function ChooseCommunityPage() {
  const router = useRouter();
  const tenants = allTenants();

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-10">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-[var(--brand-muted)]">CBS Match M7 pilot</p>
          <h1 className="mt-2 text-3xl font-semibold text-[var(--brand-text)]">Choose your community</h1>
          <p className="mt-2 text-sm text-[var(--brand-muted)]">Select your school to continue with your tenant-specific experience.</p>
        </div>
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700"
          onClick={() => {
            clearTenantClientContext();
            router.refresh();
          }}
        >
          Clear selection
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tenants.map((tenant) => (
          <button
            key={tenant.slug}
            type="button"
            onClick={() => {
              setTenantClientContext(tenant.slug);
              // Force a full navigation so server-rendered tenant theme/layout picks up cookie immediately.
              window.location.assign(`/login?tenant=${encodeURIComponent(tenant.slug)}`);
            }}
            className="group rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow"
            style={{ background: `linear-gradient(180deg, ${tenant.theme.bg} 0%, #ffffff 65%)` }}
          >
            <div className="mb-4 h-1.5 w-16 rounded-full" style={{ backgroundColor: tenant.theme.primary }} />
            <h2 className="text-lg font-semibold text-[var(--brand-text)] group-hover:underline">{tenant.name}</h2>
            <p className="mt-2 text-sm text-slate-600">{tenant.tagline}</p>
            <p className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-500">Continue as {tenant.slug.toUpperCase()}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
