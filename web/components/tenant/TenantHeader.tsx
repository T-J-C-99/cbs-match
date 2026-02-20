import { getTenantFromRequestCookie } from "@/lib/tenant-server";
import TenantHeaderActions from "@/components/tenant/TenantHeaderActions";

export default async function TenantHeader() {
  const tenant = await getTenantFromRequestCookie();
  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <div>
          <p className="text-sm font-semibold text-[var(--brand-text)]">CBS Match</p>
          <p className="text-xs text-[var(--brand-muted)]">{tenant.name}</p>
        </div>
        <TenantHeaderActions />
      </div>
    </header>
  );
}
