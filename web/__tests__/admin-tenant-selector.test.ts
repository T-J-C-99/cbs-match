import React from "react";
import { createRoot } from "react-dom/client";
import { AdminPortalProvider } from "@/components/admin/AdminPortalProvider";

jest.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({ replace: jest.fn() }),
}));

describe("Admin tenant selector", () => {
  test("loads tenants from /api/admin/tenants and renders options", async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/admin/auth/me")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admin: { id: "a1", email: "admin@cbs.com", role: "admin" } }),
        });
      }
      if (url.includes("/api/admin/tenants")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            tenants: [
              { slug: "cbs", name: "Columbia" },
              { slug: "hbs", name: "Harvard" },
              { slug: "gsb", name: "Stanford" },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    root.render(
      React.createElement(
        AdminPortalProvider,
        null,
        React.createElement("div", null, "child")
      )
    );

    await new Promise((resolve) => setTimeout(resolve, 25));
    await new Promise((resolve) => setTimeout(resolve, 25));
    await new Promise((resolve) => setTimeout(resolve, 25));

    expect(container.textContent || "").toContain("Columbia (cbs)");
    expect(container.textContent || "").toContain("Harvard (hbs)");
    expect(container.textContent || "").toContain("Stanford (gsb)");

    root.unmount();
    container.remove();
  });
});
