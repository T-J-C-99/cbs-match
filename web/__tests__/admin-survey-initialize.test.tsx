import React from "react";
import { createRoot } from "react-dom/client";

import AdminSurveyClient from "../components/AdminSurveyClient";

function setTextareaValue(el: HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
  if (setter) {
    setter.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

jest.mock("@/components/admin/AdminPortalProvider", () => {
  const state = {
    initialized: false,
    draftCreated: false,
    calls: [] as Array<{ url: string; method: string }>,
  };

  const mkRes = (status: number, body: unknown) => ({
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    text: async () => JSON.stringify(body),
  });

  return {
    useAdminPortal: () => ({
      tenantSlug: "",
      tenants: [{ slug: "cbs", name: "CBS" }],
      fetchAdmin: jest.fn(async (url: string, init?: RequestInit) => {
        const method = (init?.method || "GET").toUpperCase();
        state.calls.push({ url, method });
        if (url.startsWith("/api/admin/survey/active")) {
          if (!state.initialized) {
            return mkRes(200, { active: null, latest_draft: null, published_versions: [] });
          }
          return mkRes(200, {
              active: { id: "1", version: 1, status: "published", is_active: true, definition_json: { screens: [], option_sets: {} }, created_at: "now" },
              latest_draft: state.draftCreated
                ? { id: "2", version: 2, status: "draft", is_active: false, definition_json: { screens: [], option_sets: {} }, created_at: "now" }
                : null,
              published_versions: [{ version: 1, is_active: true }],
            });
        }
        if (url.startsWith("/api/admin/survey/draft/latest")) {
          if (!state.draftCreated) {
            return mkRes(404, { detail: "No draft survey definition found" });
          }
          return mkRes(200, {
            draft: { id: "2", version: 2, status: "draft", is_active: false, definition_json: { screens: [], option_sets: {} }, created_at: "now" },
          });
        }
        if (url.startsWith("/api/admin/survey/preview")) {
          return mkRes(200, { source: "active_db", survey: { screens: [], option_sets: {} }, active_db_survey: { screens: [], option_sets: {} }, runtime_code_survey: { screens: [], option_sets: {} } });
        }
        if (url.startsWith("/api/admin/survey/initialize-from-code") && method === "POST") {
          state.initialized = true;
          return mkRes(200, { initialized: true });
        }
        if (url.startsWith("/api/admin/survey/draft/from-active") && method === "POST") {
          state.draftCreated = true;
          return mkRes(200, { draft: { id: "2", version: 2, status: "draft", is_active: false, definition_json: { screens: [], option_sets: {} }, created_at: "now" } });
        }
        return mkRes(200, {});
      }),
    }),
    __surveyTestState: state,
  };
});

const surveyMock = jest.requireMock("@/components/admin/AdminPortalProvider") as { __surveyTestState: { calls: Array<{ url: string; method: string }> } };

describe("admin survey initialize flow", () => {
  beforeEach(() => {
    const state = (jest.requireMock("@/components/admin/AdminPortalProvider") as { __surveyTestState: { initialized: boolean; draftCreated: boolean; calls: Array<{ url: string; method: string }> } }).__surveyTestState;
    state.initialized = false;
    state.draftCreated = false;
    state.calls.length = 0;
  });

  test("renders active version after initialize from none", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(<AdminSurveyClient />);

    await new Promise((r) => setTimeout(r, 30));
    expect(container.textContent || "").toContain("Active: none");

    const initBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Initialize from code"));
    expect(initBtn).toBeTruthy();
    initBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    await new Promise((r) => setTimeout(r, 50));
    expect(container.textContent || "").toContain("Active: v1");

    root.unmount();
    container.remove();
  });

  test("create draft from active transitions latest draft from none to v2", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(<AdminSurveyClient />);

    await new Promise((r) => setTimeout(r, 40));
    const textBefore = container.textContent || "";
    expect(textBefore).toContain("Latest draft: none");

    const initBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Initialize from code"));
    initBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 40));

    const createBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Create draft from active"));
    expect(createBtn).toBeTruthy();
    createBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    await new Promise((r) => setTimeout(r, 80));
    expect(container.textContent || "").toContain("Latest draft: v2");

    root.unmount();
    container.remove();
  });

  test("invalid JSON disables save and does not call save endpoint", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(<AdminSurveyClient />);

    await new Promise((r) => setTimeout(r, 50));
    const initBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Initialize from code"));
    initBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 40));

    const createBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Create draft from active"));
    createBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 60));

    const editorTab = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.toLowerCase() === "editor");
    editorTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 10));

    const textarea = container.querySelector("textarea") as HTMLTextAreaElement | null;
    expect(textarea).toBeTruthy();
    if (textarea) {
      setTextareaValue(textarea, "{ invalid json");
    }

    await new Promise((r) => setTimeout(r, 20));
    const saveBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Save draft"));
    expect(saveBtn).toBeTruthy();
    expect(saveBtn?.hasAttribute("disabled")).toBe(true);

    const saveCalls = surveyMock.__surveyTestState.calls.filter((c) => c.method === "PUT" && c.url.startsWith("/api/admin/survey/draft/latest"));
    expect(saveCalls.length).toBe(0);

    root.unmount();
    container.remove();
  });

  test("JSON string syntax-valid but schema-invalid disables save and avoids save call", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(<AdminSurveyClient />);

    await new Promise((r) => setTimeout(r, 50));
    const initBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Initialize from code"));
    initBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 40));

    const createBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Create draft from active"));
    createBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 60));

    const editorTab = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.toLowerCase() === "editor");
    editorTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 10));

    const textarea = container.querySelector("textarea") as HTMLTextAreaElement | null;
    expect(textarea).toBeTruthy();
    if (textarea) {
      setTextareaValue(textarea, '"invalid json"');
    }

    await new Promise((r) => setTimeout(r, 30));
    expect(container.textContent || "").toContain("JSON syntax: valid");
    expect(container.textContent || "").toContain("Survey schema: invalid");

    const saveBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Save draft"));
    expect(saveBtn?.hasAttribute("disabled")).toBe(true);

    const saveCalls = surveyMock.__surveyTestState.calls.filter((c) => c.method === "PUT" && c.url.startsWith("/api/admin/survey/draft/latest"));
    expect(saveCalls.length).toBe(0);

    root.unmount();
    container.remove();
  });

  test("empty object is schema-invalid and valid survey object enables save", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    root.render(<AdminSurveyClient />);

    await new Promise((r) => setTimeout(r, 50));
    const initBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Initialize from code"));
    initBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 40));

    const createBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Create draft from active"));
    createBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 60));

    const editorTab = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.toLowerCase() === "editor");
    editorTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 10));

    const textarea = container.querySelector("textarea") as HTMLTextAreaElement | null;
    expect(textarea).toBeTruthy();
    if (textarea) {
      setTextareaValue(textarea, "{}");
    }

    await new Promise((r) => setTimeout(r, 20));
    expect(container.textContent || "").toContain("Survey schema: invalid");
    let saveBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Save draft"));
    expect(saveBtn?.hasAttribute("disabled")).toBe(true);

    if (textarea) {
      setTextareaValue(
        textarea,
        JSON.stringify({ screens: [{ key: "k1", items: [] }], option_sets: {} }, null, 2),
      );
    }

    await new Promise((r) => setTimeout(r, 30));
    expect(container.textContent || "").toContain("Survey schema: valid");
    saveBtn = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Save draft"));
    expect(saveBtn?.hasAttribute("disabled")).toBe(false);
    saveBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    await new Promise((r) => setTimeout(r, 30));
    const saveCalls = surveyMock.__surveyTestState.calls.filter((c) => c.method === "PUT" && c.url.startsWith("/api/admin/survey/draft/latest"));
    expect(saveCalls.length).toBe(1);

    root.unmount();
    container.remove();
  });
});
