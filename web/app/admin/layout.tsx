import { AdminPortalProvider } from "@/components/admin/AdminPortalProvider";
import type { ReactNode } from "react";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <AdminPortalProvider>{children}</AdminPortalProvider>;
}
