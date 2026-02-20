"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";

export default function VerifyPage() {
  const { verifyEmail, resendVerificationCode } = useAuth();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("Enter your email and 6-digit verification code.");
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const qs = new URLSearchParams(window.location.search);
    const emailParam = qs.get("email") || "";
    const codeParam = qs.get("code") || "";
    setEmail(emailParam);
    setCode(codeParam);
  }, []);

  const runVerify = async (emailValue: string, codeValue: string) => {
    const normalizedEmail = emailValue.trim().toLowerCase();
    const trimmedCode = codeValue.trim();
    if (!normalizedEmail) {
      setMessage("Missing email");
      return;
    }
    if (!/^\d{6}$/.test(trimmedCode)) {
      setMessage("Code must be exactly 6 digits");
      return;
    }

    setVerifying(true);
    try {
      await verifyEmail(normalizedEmail, trimmedCode);
      setMessage("Email verified. You can login now.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  };

  const runResend = async (emailValue: string) => {
    const normalizedEmail = emailValue.trim().toLowerCase();
    if (!normalizedEmail) {
      setMessage("Enter your email first to resend code");
      return;
    }
    setResending(true);
    try {
      const result = await resendVerificationCode(normalizedEmail);
      const devCode = result?.dev_only?.verification_code;
      if (devCode) {
        setCode(String(devCode));
        setMessage(`New code sent. (DEV) Your code is ${String(devCode)}.`);
      } else {
        setMessage(result?.message || "If the account exists, a new verification code was sent.");
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not resend verification code");
    } finally {
      setResending(false);
    }
  };

  useEffect(() => {
    if (!email || !code) return;
    if (!/^\d{6}$/.test(code.trim())) return;
    runVerify(email, code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email, code]);

  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-semibold">Verify email</h1>
      <p className="mt-3 text-sm text-slate-700">{message}</p>
      <div className="mt-4 space-y-2">
        <input
          className="w-full rounded border px-3 py-2"
          placeholder="you@gsb.columbia.edu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="w-full rounded border px-3 py-2"
          placeholder="6-digit code"
          value={code}
          maxLength={6}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        />
        <button
          className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-60"
          type="button"
          disabled={verifying}
          onClick={() => runVerify(email, code)}
        >
          {verifying ? "Verifying..." : "Verify code"}
        </button>
        <button
          className="w-full rounded border px-4 py-2 disabled:opacity-60"
          type="button"
          disabled={resending}
          onClick={() => runResend(email)}
        >
          {resending ? "Sending..." : "Resend code"}
        </button>
      </div>
      <p className="mt-4 text-sm"><a className="underline" href="/login">Go to login</a></p>
    </div>
  );
}
