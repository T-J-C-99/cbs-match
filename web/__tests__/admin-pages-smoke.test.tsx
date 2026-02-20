import React from "react";
import { renderToString } from "react-dom/server";

jest.mock("@/components/admin/AdminPortalProvider", () => ({
  useAdminPortal: () => ({
    tenantSlug: "",
    tenants: [{ slug: "cbs", name: "CBS" }],
    fetchAdmin: jest.fn(async () => ({ ok: true, json: async () => ({ by_tenant: [], assignments: [], totals: {}, counts: {} }) })),
  }),
}));

describe("admin page smoke tests", () => {
  test("matching page renders", async () => {
    const Page = (await import("@/app/admin/matching/page")).default;
    const html = renderToString(<Page />);
    expect(html).toContain("Matching operations");
  });

  test("safety page renders", async () => {
    const Page = (await import("@/app/admin/safety/page")).default;
    const html = renderToString(<Page />);
    expect(html).toContain("Safety reports");
  });

  test("notifications page renders", async () => {
    const Page = (await import("@/app/admin/notifications/page")).default;
    const html = renderToString(<Page />);
    expect(html).toContain("Notifications outbox v2");
  });

  test("metrics page renders", async () => {
    const Page = (await import("@/app/admin/metrics/page")).default;
    const html = renderToString(<Page />);
    expect(html).toContain("Metrics dashboard");
  });

  test("calibration page renders", async () => {
    const Page = (await import("@/app/admin/calibration/page")).default;
    const html = renderToString(<Page />);
    expect(html).toContain("Calibration report");
  });

  test("survey admin client renders", async () => {
    const Page = (await import("@/components/AdminSurveyClient")).default;
    const html = renderToString(<Page />);
    expect(html).toContain("Survey administration");
  });
});
