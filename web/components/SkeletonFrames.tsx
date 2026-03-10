"use client";

type Props = { className?: string };

export function SkeletonBlock({ className = "" }: Props) {
  return <div className={`cbs-skeleton ${className}`.trim()} aria-hidden="true" />;
}

export function AuthGateSkeleton() {
  return (
    <div className="cbs-page-shell">
      <SkeletonBlock className="h-5 w-28" />
      <div className="mt-6 rounded-full border border-cbs-columbia bg-white p-1 shadow-sm">
        <div className="grid grid-cols-4 gap-2">
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
        </div>
      </div>
      <div className="mt-8 space-y-4">
        <SkeletonBlock className="h-10 w-64" />
        <SkeletonBlock className="h-4 w-80" />
      </div>
      <div className="mt-6 space-y-4">
        <SkeletonBlock className="h-72 w-full rounded-xl" />
        <SkeletonBlock className="h-72 w-full rounded-xl" />
      </div>
    </div>
  );
}

export function PastMatchesSkeleton() {
  return (
    <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="overflow-hidden rounded-xl border border-cbs-columbia bg-white shadow-sm">
          <div className="grid grid-cols-[minmax(140px,58%)_1fr]">
            <SkeletonBlock className="h-72 w-full sm:h-80" />
            <div className="space-y-3 p-4">
              <SkeletonBlock className="h-7 w-3/4" />
              <SkeletonBlock className="h-4 w-1/2" />
              <SkeletonBlock className="h-5 w-2/3" />
              <div className="mt-2 flex gap-2">
                <SkeletonBlock className="h-8 w-8 rounded-lg" />
                <SkeletonBlock className="h-8 w-8 rounded-lg" />
                <SkeletonBlock className="h-8 w-8 rounded-lg" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SurveySkeleton() {
  return (
    <div className="mx-auto max-w-3xl p-6">
      <SkeletonBlock className="h-4 w-36" />
      <SkeletonBlock className="mt-3 h-2 w-full" />
      <SkeletonBlock className="mt-7 h-8 w-72" />
      <SkeletonBlock className="mt-2 h-4 w-2/3" />
      <div className="mt-6 space-y-6">
        {[0, 1, 2].map((idx) => (
          <div key={idx} className="rounded border border-slate-200 bg-white p-4">
            <SkeletonBlock className="h-5 w-3/4" />
            <div className="mt-3 space-y-2">
              <SkeletonBlock className="h-10 w-full" />
              <SkeletonBlock className="h-10 w-full" />
              <SkeletonBlock className="h-10 w-5/6" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PageShellSkeleton() {
  return (
    <div className="cbs-page-shell">
      <SkeletonBlock className="h-5 w-28" />
      <div className="mt-6 rounded-full border border-cbs-columbia bg-white p-1 shadow-sm">
        <div className="grid grid-cols-4 gap-2">
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
        </div>
      </div>
      <div className="mt-8 space-y-3">
        <SkeletonBlock className="h-10 w-64" />
        <SkeletonBlock className="h-4 w-80" />
      </div>
      <div className="mt-6 space-y-4">
        <SkeletonBlock className="h-44 w-full rounded-xl" />
        <SkeletonBlock className="h-44 w-full rounded-xl" />
      </div>
    </div>
  );
}

export function MatchPageSkeleton() {
  return (
    <div className="cbs-page-shell">
      <SkeletonBlock className="h-5 w-28" />
      <div className="mt-6 rounded-full border border-cbs-columbia bg-white p-1 shadow-sm">
        <div className="grid grid-cols-4 gap-2">
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
          <SkeletonBlock className="h-10 rounded-full" />
        </div>
      </div>
      <div className="mt-8 flex items-start justify-between gap-4">
        <div className="space-y-3">
          <SkeletonBlock className="h-10 w-64" />
        </div>
        <SkeletonBlock className="h-4 w-36" />
      </div>
      <div className="mt-6 overflow-hidden rounded-2xl border border-cbs-columbia bg-white shadow-sm">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(260px,42%)_1fr]">
          <SkeletonBlock className="h-[360px] w-full" />
          <div className="space-y-4 p-6">
            <SkeletonBlock className="h-6 w-40" />
            <SkeletonBlock className="h-8 w-56" />
            <SkeletonBlock className="h-4 w-2/3" />
            <SkeletonBlock className="h-4 w-1/2" />
            <div className="pt-2 flex gap-2">
              <SkeletonBlock className="h-10 w-28 rounded-full" />
              <SkeletonBlock className="h-10 w-28 rounded-full" />
            </div>
          </div>
        </div>
      </div>
      <div className="mt-6 rounded-xl border border-cbs-columbia bg-white p-5 shadow-sm space-y-3">
        <SkeletonBlock className="h-6 w-48" />
        <SkeletonBlock className="h-4 w-full" />
        <SkeletonBlock className="h-4 w-11/12" />
        <SkeletonBlock className="h-4 w-10/12" />
      </div>
    </div>
  );
}
