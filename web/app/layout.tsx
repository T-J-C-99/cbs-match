import "./globals.css";
import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import { getTenantFromRequestCookie } from "@/lib/tenant-server";
import { tenantCssVars } from "@/lib/theme";
import TenantHeader from "@/components/tenant/TenantHeader";

export const metadata: Metadata = {
  title: "CBS Match",
  description: "Questionnaire app",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const tenant = await getTenantFromRequestCookie();
  return (
    <html lang="en" data-tenant={tenant.slug} style={tenantCssVars(tenant)}>
      <body>
        <AuthProvider>
          <TenantHeader />
          <main className="min-h-screen">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
