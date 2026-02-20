"use client";

import { useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function AppShellNav() {
  const pathname = usePathname();

  const tabs = useMemo(() => {
    return [
      { href: "/match", label: "Match" },
      { href: "/past", label: "Past" },
      { href: "/profile", label: "Profile" },
      { href: "/settings", label: "Settings" },
    ];
  }, []);

  return (
    <nav className="mb-8 flex items-center justify-between gap-4">
      <div>
        <p className="text-xs uppercase tracking-[0.14em] text-cbs-slate">CBS Match</p>
      </div>
      <div className="flex items-center gap-2 rounded-full border border-cbs-columbia bg-white p-1 shadow-sm">
        {tabs.map((tab) => {
          const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                active ? "bg-cbs-navy text-white" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
