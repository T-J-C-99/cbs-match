"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { getTenantBySlug } from "@cbs-match/shared";
import { getTenantFromClientStorage, setTenantClientContext } from "@/lib/tenant";

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [usernameStatus, setUsernameStatus] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
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

  const checkUsername = async (raw: string) => {
    const value = raw.trim().toLowerCase();
    if (!value) {
      setUsernameStatus(null);
      return;
    }
    if (!/^[a-z0-9_]{3,24}$/.test(value)) {
      setUsernameStatus("Use 3-24 lowercase letters, numbers, or underscores.");
      return;
    }
    const res = await fetch(`/api/auth/username-availability?username=${encodeURIComponent(value)}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setUsernameStatus(data.detail || "Could not check username");
      return;
    }
    setUsernameStatus(data.available ? "Username is available." : "Username is taken.");
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({
        email,
        password,
        username: username.trim().toLowerCase() || undefined,
      });
      setMessage("Account created. Next: complete your survey, then finish profile details.");
      router.push("/welcome");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Register failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-6">
      <h1 className="text-2xl font-semibold">Create account · {tenantLabel}</h1>
      <p className="mt-1 text-sm text-slate-600">Use your {suggestedDomain} school address.</p>
      <form className="mt-4 space-y-3" onSubmit={onSubmit}>
        <input className="w-full rounded border px-3 py-2" placeholder={`you@${suggestedDomain}`} value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full rounded border px-3 py-2" placeholder="username (optional)" value={username} onChange={(e) => setUsername(e.target.value)} onBlur={() => checkUsername(username)} />
        {usernameStatus && <p className="text-xs text-slate-600">{usernameStatus}</p>}
        <input className="w-full rounded border px-3 py-2" type={showPassword ? "text" : "password"} placeholder="Password (min 10 chars)" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="button" className="text-sm text-slate-600 underline" onClick={() => setShowPassword((v) => !v)}>{showPassword ? "Hide password" : "Show password"}</button>
        <button className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-60" type="submit" disabled={loading}>{loading ? "Creating..." : "Create account"}</button>
      </form>
      {message && <p className="mt-3 text-sm text-green-700">{message}</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <p className="mt-4 text-sm"><a className="underline" href={`/login${tenantSlug ? `?tenant=${encodeURIComponent(tenantSlug)}` : ""}`}>Already have an account? Login</a></p>
      <p className="mt-2 text-sm"><a className="underline" href="/landing">Back to landing</a></p>
    </div>
  );
}
