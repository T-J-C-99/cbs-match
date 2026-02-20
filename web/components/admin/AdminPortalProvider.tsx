"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { normalizeAdminTenantSelection } from "@/lib/admin-tenant-scope";

type AdminUser = { id: string; email: string; role: string };
type Tenant = { slug: string; name: string; disabled_at?: string | null };

type AdminPortalContextValue = {
  admin: AdminUser | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  tenantSlug: string;
  setTenantSlug: (value: string) => void;
  tenants: Tenant[];
  refreshTenants: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchAdmin: (input: string, init?: RequestInit) => Promise<Response>;
};

const TOKEN_KEY = "cbs_admin_token";
const TENANT_KEY = "cbs_admin_tenant_slug";

const AdminPortalContext = createContext<AdminPortalContextValue | null>(null);

const NAV: Array<{ label: string; href: string }> = [
  { label: "Dashboard", href: "/admin" },
  { label: "Tenants", href: "/admin/tenants" },
  { label: "Users", href: "/admin/users" },
  { label: "Matching", href: "/admin/matching" },
  { label: "Surveys", href: "/admin/surveys" },
  { label: "Safety", href: "/admin/safety" },
  { label: "Notifications", href: "/admin/notifications" },
  { label: "Metrics", href: "/admin/metrics" },
  { label: "Calibration", href: "/admin/calibration" },
];

async function parseJson(res: Response) {
  return res.json().catch(() => ({}));
}

export function AdminPortalProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantSlug, setTenantSlugState] = useState<string>("");

  const setTenantSlug = (value: string) => {
    const normalized = normalizeAdminTenantSelection(value, tenants.map((t) => t.slug));
    setTenantSlugState(normalized);
    if (typeof window !== "undefined") {
      localStorage.setItem(TENANT_KEY, normalized);
    }
  };

  const refreshAuth = async () => {
    const res = await fetch("/api/admin/auth/me", { cache: "no-store" });
    const data = await parseJson(res);
    if (!res.ok) {
      setAdmin(null);
      return;
    }
    setAdmin((data?.admin as AdminUser) || null);
  };

  const refreshTenants = async () => {
    const res = await fetch("/api/admin/tenants", { cache: "no-store" });
    const data = await parseJson(res);
    if (!res.ok) return;
    const nextTenants = Array.isArray(data?.tenants) ? data.tenants : [];
    setTenants(nextTenants);
    const validSlugs = nextTenants.map((t: Tenant) => t.slug);
    setTenantSlugState((prev) => {
      const normalized = normalizeAdminTenantSelection(prev, validSlugs);
      if (typeof window !== "undefined") {
        localStorage.setItem(TENANT_KEY, normalized);
      }
      return normalized;
    });
  };

  useEffect(() => {
    const storedToken = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    const storedTenantRaw = typeof window !== "undefined" ? localStorage.getItem(TENANT_KEY) || "" : "";
    const storedTenant = normalizeAdminTenantSelection(storedTenantRaw);
    setToken(storedToken);
    setTenantSlugState(storedTenant);

    refreshAuth()
      .then(refreshTenants)
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pathname !== "/admin/login" && !loading && !admin) {
      router.replace("/admin/login");
    }
  }, [pathname, loading, admin, router]);

  const login = async (email: string, password: string) => {
    const res = await fetch("/api/admin/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await parseJson(res);
    if (!res.ok) {
      throw new Error(data?.detail || "Login failed");
    }
    const nextToken = String(data?.access_token || "");
    if (nextToken && typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, nextToken);
      setToken(nextToken);
    }
    setAdmin((data?.admin as AdminUser) || null);
    await refreshTenants();
  };

  const logout = async () => {
    await fetch("/api/admin/auth/logout", { method: "POST" });
    setAdmin(null);
    setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
    }
    router.replace("/admin/login");
  };

  const fetchAdmin = async (input: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers || {});
    if (token && !headers.get("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return fetch(input, { ...init, headers });
  };

  const value = useMemo<AdminPortalContextValue>(
    () => ({
      admin,
      token,
      loading,
      isAuthenticated: !!admin,
      tenantSlug,
      setTenantSlug,
      tenants,
      refreshTenants,
      login,
      logout,
      fetchAdmin,
    }),
    [admin, token, loading, tenantSlug, tenants]
  );

  if (pathname === "/admin/login") {
    return <AdminPortalContext.Provider value={value}>{children}</AdminPortalContext.Provider>;
  }

  if (loading) {
    return (
      <AdminPortalContext.Provider value={value}>
        <div className="mx-auto max-w-3xl p-6 text-sm text-slate-600">Loading admin portal…</div>
      </AdminPortalContext.Provider>
    );
  }

  return (
    <AdminPortalContext.Provider value={value}>
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 p-6 md:grid-cols-[220px_1fr]">
        <aside className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Admin Portal</h2>
          <nav className="mt-3 space-y-1 text-sm">
            {NAV.map((item) => (
              <Link
                key={item.href}
                className={`block rounded px-2 py-1.5 hover:bg-slate-100 ${pathname === item.href ? "bg-slate-100 font-medium" : ""}`}
                href={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <section>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-slate-600">Tenant:</span>
              <select
                className="rounded border border-slate-300 bg-white px-2 py-1"
                value={tenantSlug}
                onChange={(e) => setTenantSlug(e.target.value)}
              >
                <option value="">All tenants</option>
                {tenants.map((t) => (
                  <option key={t.slug} value={t.slug}>
                    {t.name} ({t.slug})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-slate-700">
                {admin?.email || ""} {admin?.role ? `(${admin.role})` : ""}
              </span>
              <button className="rounded border border-slate-300 px-2 py-1" onClick={logout}>
                Logout
              </button>
            </div>
          </div>
          {children}
        </section>
      </div>
    </AdminPortalContext.Provider>
  );
}

export function useAdminPortal() {
  const ctx = useContext(AdminPortalContext);
  if (!ctx) throw new Error("useAdminPortal must be used inside AdminPortalProvider");
  return ctx;
}
