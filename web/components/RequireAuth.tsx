"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { apiGet, formatError } from "@/lib/apiClient";

type GuardState = {
  checked: boolean;
  hasCompletedSurvey: boolean;
  hasRequiredProfile: boolean;
};

export default function RequireAuth({
  children,
  requireVerified = false,
  requireCompletedSurvey = false,
  requireCompleteProfile = false,
}: {
  children: React.ReactNode;
  requireVerified?: boolean;
  requireCompletedSurvey?: boolean;
  requireCompleteProfile?: boolean;
}) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [guardState, setGuardState] = useState<GuardState>({
    checked: !(requireCompletedSurvey || requireCompleteProfile),
    hasCompletedSurvey: false,
    hasRequiredProfile: false,
  });

  useEffect(() => {
    setGuardState({
      checked: !(requireCompletedSurvey || requireCompleteProfile),
      hasCompletedSurvey: false,
      hasRequiredProfile: false,
    });
  }, [requireCompletedSurvey, requireCompleteProfile, user?.id]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    // Email verification is deprecated in current UX.

    if (!requireCompletedSurvey && !requireCompleteProfile) {
      return;
    }

    let cancelled = false;

    const checkState = async () => {
      try {
        const data = await apiGet<{
          onboarding?: { has_completed_survey?: boolean };
          profile?: { has_required_profile?: boolean };
        }>("/users/me/state");

        if (cancelled) return;

        const hasCompletedSurvey = Boolean(data?.onboarding?.has_completed_survey);
        const hasRequiredProfile = Boolean(data?.profile?.has_required_profile);
        setGuardState({ checked: true, hasCompletedSurvey, hasRequiredProfile });

        if (requireCompletedSurvey && !hasCompletedSurvey) {
          router.replace("/welcome");
          return;
        }
        if (requireCompleteProfile && !hasRequiredProfile) {
          router.replace("/profile?required=1");
        }
      } catch (error) {
        if (cancelled) return;
        console.error("[RequireAuth] Failed to check state:", formatError(error));
        router.replace("/welcome");
      }
    };

    checkState();
    return () => {
      cancelled = true;
    };
  }, [
    loading,
    user,
    requireVerified,
    requireCompletedSurvey,
    requireCompleteProfile,
    router,
  ]);

  const blockedForVerification = false;
  const blockedForSurvey = requireCompletedSurvey && guardState.checked && !guardState.hasCompletedSurvey;
  const blockedForProfile = requireCompleteProfile && guardState.checked && !guardState.hasRequiredProfile;

  if (
    loading ||
    !user ||
    blockedForVerification ||
    ((requireCompletedSurvey || requireCompleteProfile) && !guardState.checked) ||
    blockedForSurvey ||
    blockedForProfile
  ) {
    return <div className="mx-auto max-w-2xl p-6">Loading...</div>;
  }

  return <>{children}</>;
}