"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { getTenantBySlug } from "@cbs-match/shared";
import { getTenantFromClientStorage, setTenantClientContext } from "@/lib/tenant";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const tenantSlug = (searchParams.get("tenant") || "").toLowerCase();

  useEffect(() => {
    if (!tenantSlug) return;
    const tenant = getTenantBySlug(tenantSlug);
    if (tenant) setTenantClientContext(tenant.slug);
  }, [tenantSlug]);

  const selectedTenant = useMemo(() => {
    return getTenantBySlug(tenantSlug) ?? getTenantFromClientStorage();
  }, [tenantSlug]);

  const suggestedDomain = selectedTenant.emailDomains?.[0] || "gsb.columbia.edu";
  const tenantLabel = selectedTenant.slug.toUpperCase();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier, password);
      router.push("/welcome");
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Login failed";
      if (raw === "Invalid credentials") {
        setError("Incorrect email or password.");
      } else {
        setError(raw);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-6">
      <h1 className="text-2xl font-semibold">Login · {tenantLabel}</h1>
      <p className="mt-1 text-sm text-slate-600">Access your community account with email or username.</p>
      <form className="mt-4 space-y-3" onSubmit={onSubmit}>
        <input className="w-full rounded border px-3 py-2" placeholder={`you@${suggestedDomain} or username`} value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
        <input className="w-full rounded border px-3 py-2" type={showPassword ? "text" : "password"} placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="button" className="text-sm text-slate-600 underline" onClick={() => setShowPassword((v) => !v)}>{showPassword ? "Hide password" : "Show password"}</button>
        <button className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-60" type="submit" disabled={loading}>{loading ? "Logging in..." : "Login"}</button>
      </form>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <p className="mt-4 text-sm"><a className="underline" href={`/register${tenantSlug ? `?tenant=${encodeURIComponent(tenantSlug)}` : ""}`}>Need an account? Register</a></p>
      <p className="mt-2 text-sm"><a className="underline" href="/landing">Back to landing</a></p>
    </div>
  );
}
