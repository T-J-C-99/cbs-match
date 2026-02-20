"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";

export default function AdminLoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, loading } = useAdminPortal();
  const [email, setEmail] = useState("admin@cbsmatch.local");
  const [password, setPassword] = useState("community123");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.replace("/admin");
    }
  }, [loading, isAuthenticated, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto mt-16 max-w-md rounded border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold">Admin Login</h1>
      <p className="mt-1 text-sm text-slate-600">Sign in to manage communities, matching, and operations.</p>
      <form className="mt-4 space-y-3" onSubmit={submit}>
        <label className="block text-sm">
          <div className="mb-1">Email</div>
          <input className="w-full rounded border border-slate-300 px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm">
          <div className="mb-1">Password</div>
          <input type="password" className="w-full rounded border border-slate-300 px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error ? <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        <button disabled={submitting} className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-60">
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
