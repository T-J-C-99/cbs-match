import React from "react";
import { createRoot } from "react-dom/client";

let currentTenant = "";

jest.mock("@/components/admin/AdminPortalProvider", () => ({
  useAdminPortal: () => ({
    tenantSlug: currentTenant,
  }),
}));

describe("Admin dashboard tenant scope query", () => {
  test("omits tenant_slug for All tenants", async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/admin/dashboard")) {
        return Promise.resolve({ ok: true, json: async () => ({ kpis: {}, recent_activity: {} }) });
      }
      if (url.startsWith("/api/admin/diagnostics")) {
        return Promise.resolve({ ok: true, json: async () => ({ tenants_count: 7, by_tenant: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    currentTenant = "";
    const Page = (await import("../app/admin/page")).default;
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(React.createElement(Page));
    await new Promise((resolve) => setTimeout(resolve, 25));

    const dashboardUrl = (fetchMock.mock.calls.find((c) => String(c[0]).startsWith("/api/admin/dashboard")) || [""])[0] as string;
    expect(dashboardUrl).toBe("/api/admin/dashboard");

    root.unmount();
    container.remove();
  });

  test("includes tenant_slug for specific tenant", async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/admin/dashboard")) {
        return Promise.resolve({ ok: true, json: async () => ({ kpis: {}, recent_activity: {} }) });
      }
      if (url.startsWith("/api/admin/diagnostics")) {
        return Promise.resolve({ ok: true, json: async () => ({ tenants_count: 7, by_tenant: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    currentTenant = "cbs";
    const Page = (await import("../app/admin/page")).default;
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(React.createElement(Page));
    await new Promise((resolve) => setTimeout(resolve, 25));

    const dashboardUrl = (fetchMock.mock.calls.find((c) => String(c[0]).startsWith("/api/admin/dashboard")) || [""])[0] as string;
    expect(dashboardUrl).toContain("tenant_slug=cbs");

    root.unmount();
    container.remove();
  });
});
