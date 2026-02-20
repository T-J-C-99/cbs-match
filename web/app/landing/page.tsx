"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function LandingPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    router.replace("/choose");
  }, [router]);

  useEffect(() => {
    if (loading) return;
    if (user?.is_email_verified) {
      router.replace("/welcome");
    }
  }, [loading, user, router]);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col items-center justify-center px-6 text-center">
      <p className="rounded-full border border-slate-200 bg-white px-4 py-1 text-xs uppercase tracking-wide text-slate-600">CBS Match Pilot</p>
      <h1 className="mt-6 text-4xl font-semibold tracking-tight text-slate-900">Find your best match at CBS</h1>
      <p className="mt-4 max-w-2xl text-slate-600">
        Start with account creation, complete one required survey, and move into your stable home experience with matches, chat, and profile.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link href="/register" className="rounded bg-black px-5 py-2.5 font-medium text-white">Create account</Link>
        <Link href="/login" className="rounded border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-900">Log in</Link>
      </div>

      <div className="mt-10 grid w-full max-w-3xl grid-cols-1 gap-3 text-left md:grid-cols-3">
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="font-medium">1) Onboard</h2>
          <p className="mt-2 text-sm text-slate-600">Create account and verify your CBS email.</p>
        </div>
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="font-medium">2) Survey</h2>
          <p className="mt-2 text-sm text-slate-600">Complete the full required survey to unlock matching.</p>
        </div>
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="font-medium">3) Home</h2>
          <p className="mt-2 text-sm text-slate-600">Check matches, start chats, and manage profile in one place.</p>
        </div>
      </div>
    </div>
  );
}
