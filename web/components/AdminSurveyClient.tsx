"use client";

import { useEffect, useMemo, useState } from "react";
import SurveyPreview from "@/components/SurveyPreview";
import { type SurveySchema } from "@cbs-match/shared";
import { useAdminPortal } from "@/components/admin/AdminPortalProvider";

type DefinitionRecord = {
  id: string;
  slug: string;
  version: number;
  status: "draft" | "published";
  is_active: boolean;
  definition_json: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
};

type PublishedVersion = {
  id: string;
  version: number;
  is_active: boolean;
  created_at?: string;
};

type RequestLog = {
  id: string;
  at: string;
  method: string;
  url: string;
  status?: number;
  ok: boolean;
  requestBody?: string;
  responseBody?: string;
  error?: string;
};

type PreviewPayload = {
  source: "active_db" | "runtime_code";
  survey: Record<string, unknown> | null;
  active_db_survey: Record<string, unknown> | null;
  runtime_code_survey: Record<string, unknown> | null;
};

type ApiErrorState = {
  status?: number;
  requestId?: string | null;
  message: string;
  errors?: Array<{ path: string; message: string; code?: string }>;
};

type ParseErrorState = { message: string; line?: number; column?: number };
type SaveStatus = "idle" | "dirty" | "saving" | "saved" | "error";

function stableStringify(v: unknown) { return JSON.stringify(v, null, 2); }
function trimBody(value: unknown, max = 500) {
  const text = typeof value === "string" ? value : stableStringify(value);
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function countSurvey(definition: Record<string, unknown> | null) {
  const screens = Array.isArray(definition?.screens) ? definition.screens : [];
  const questions = screens.reduce((sum, screen) => {
    const screenItems = screen as { items?: unknown[] };
    const items = Array.isArray(screenItems?.items) ? screenItems.items : [];
    return sum + items.length;
  }, 0);
  return { sections: screens.length, questions };
}

function parseJsonWithPosition(rawText: string): { value: unknown | null; error: ParseErrorState | null } {
  try {
    return { value: JSON.parse(rawText), error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const posMatch = message.match(/position\s+(\d+)/i);
    if (!posMatch) return { value: null, error: { message } };
    const pos = Number(posMatch[1]);
    if (!Number.isFinite(pos) || pos < 0) return { value: null, error: { message } };
    const upto = rawText.slice(0, pos);
    const lines = upto.split("\n");
    const line = lines.length;
    const column = (lines[lines.length - 1]?.length || 0) + 1;
    return { value: null, error: { message, line, column } };
  }
}

function getSchemaError(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return "Survey definition must be a JSON object, not a JSON string/array.";
  }
  const obj = value as Record<string, unknown>;
  const hasScreens = Array.isArray(obj.screens);
  const hasSections = Array.isArray(obj.sections);
  const hasDefinition = typeof obj.definition === "object" && obj.definition !== null && !Array.isArray(obj.definition);
  if (!hasScreens && !hasSections && !hasDefinition) {
    return "Survey definition missing required keys: screens (array) or sections (array) or definition (object).";
  }
  return null;
}

function extractErrorDetail(data: Record<string, unknown>, fallbackText: string) {
  const detail = data?.detail as Record<string, unknown> | string | undefined;
  const message = typeof detail === "string"
    ? detail
    : String((detail as Record<string, unknown> | undefined)?.message || fallbackText);
  const errors = Array.isArray((detail as Record<string, unknown> | undefined)?.errors)
    ? ((detail as Record<string, unknown>).errors as Array<{ path: string; message: string; code?: string }>)
    : [];
  const traceId = typeof detail === "string" ? null : (detail as Record<string, unknown> | undefined)?.trace_id;
  return { message, errors, traceId };
}

export default function AdminSurveyClient() {
  const { tenantSlug, tenants, fetchAdmin } = useAdminPortal();
  const [active, setActive] = useState<DefinitionRecord | null>(null);
  const [draft, setDraft] = useState<DefinitionRecord | null>(null);
  const [publishedVersions, setPublishedVersions] = useState<PublishedVersion[]>([]);
  const [jsonText, setJsonText] = useState<string>("");
  const [savedDraftText, setSavedDraftText] = useState<string>("");
  const [message, setMessage] = useState<string>("");
  const [apiError, setApiError] = useState<ApiErrorState | null>(null);
  const [tab, setTab] = useState<"overview" | "editor" | "diff" | "preview">("overview");
  const [preview, setPreview] = useState<PreviewPayload>({ source: "runtime_code", survey: null, active_db_survey: null, runtime_code_survey: null });
  const [previewSourceView, setPreviewSourceView] = useState<"active_db" | "runtime_code">("active_db");
  const [previewTenantSlug, setPreviewTenantSlug] = useState<string>("");
  const [rollbackVersion, setRollbackVersion] = useState<string>("");
  const [requestLogs, setRequestLogs] = useState<RequestLog[]>([]);
  const [debugEnabled, setDebugEnabled] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");

  const parseResult = useMemo(() => parseJsonWithPosition(jsonText), [jsonText]);
  const parsedJson = parseResult.value;
  const parseError = parseResult.error;
  const schemaError = useMemo(() => (parseError ? null : getSchemaError(parsedJson)), [parseError, parsedJson]);
  const parsedDraft = useMemo(() => (parseError || schemaError || !parsedJson ? null : (parsedJson as SurveySchema)), [parseError, schemaError, parsedJson]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const enabled = new URLSearchParams(window.location.search).get("debug") === "1";
    setDebugEnabled(enabled);
  }, []);

  const trackLog = (entry: RequestLog) => {
    setRequestLogs((prev) => [entry, ...prev].slice(0, 10));
    if (debugEnabled) {
      // Temporary debugging instrumentation requested for survey admin wiring.
      console.log("[surveys-admin][request]", entry);
    }
  };

  const request = async (url: string, init?: RequestInit) => {
    const method = (init?.method || "GET").toUpperCase();
    const requestBody = init?.body ? trimBody(String(init.body), 300) : undefined;
    try {
      const res = await fetchAdmin(url, init);
      const text = await res.text();
      let data: Record<string, unknown> = {};
      try {
        data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      } catch {
        data = {};
      }
      trackLog({
        id: `${Date.now()}-${Math.random()}`,
        at: new Date().toISOString(),
        method,
        url,
        status: res.status,
        ok: res.ok,
        requestBody,
        responseBody: trimBody(text, 500),
      });
      return { ok: res.ok, status: res.status, data, text, requestId: res.headers.get("x-request-id") };
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error);
      trackLog({
        id: `${Date.now()}-${Math.random()}`,
        at: new Date().toISOString(),
        method,
        url,
        ok: false,
        requestBody,
        error: messageText,
      });
      throw error;
    }
  };

  const loadState = async () => {
    try {
      const res = await request("/api/admin/survey/active", { cache: "no-store" });
      if (!res.ok) {
        const detail = extractErrorDetail(res.data, res.text ? trimBody(res.text, 500) : "Failed to load survey state");
        setApiError({
          status: res.status,
          requestId: res.requestId || (typeof detail.traceId === "string" ? detail.traceId : null),
          message: detail.message,
          errors: detail.errors,
        });
        return;
      }
      const nextActive = (res.data.active as DefinitionRecord | null) || null;
      const nextDraft = (res.data.latest_draft as DefinitionRecord | null) || null;
      const versions = Array.isArray(res.data.published_versions) ? (res.data.published_versions as PublishedVersion[]) : [];
      setActive(nextActive);
      setDraft(nextDraft);
      setPublishedVersions(versions);
      if (nextDraft?.definition_json) {
        const nextText = stableStringify(nextDraft.definition_json);
        setJsonText(nextText);
        setSavedDraftText(nextText);
        setSaveStatus("idle");
      } else if (nextActive?.definition_json) {
        const activeText = stableStringify(nextActive.definition_json);
        setJsonText(activeText);
        setSavedDraftText(activeText);
        setSaveStatus("idle");
      }
      setApiError(null);
    } catch (error) {
      setApiError({ message: error instanceof Error ? error.message : "Failed to load survey state" });
    }
  };

  const loadLatestDraft = async () => {
    try {
      const res = await request("/api/admin/survey/draft/latest", { cache: "no-store" });
      if (!res.ok) {
        if (res.status === 404) {
          setDraft(null);
          setSavedDraftText("");
          return;
        }
        const detail = extractErrorDetail(res.data, res.text ? trimBody(res.text, 500) : "Failed to load latest draft");
        setApiError({ status: res.status, requestId: res.requestId || (typeof detail.traceId === "string" ? detail.traceId : null), message: detail.message, errors: detail.errors });
        return;
      }
      const latest = (res.data.draft as DefinitionRecord | null) || null;
      setDraft(latest);
      if (latest?.definition_json) {
        const nextText = stableStringify(latest.definition_json);
        setJsonText(nextText);
        setSavedDraftText(nextText);
        setSaveStatus("idle");
      }
    } catch (error) {
      setApiError({ message: error instanceof Error ? error.message : "Failed to load latest draft" });
    }
  };

  const loadPreview = async () => {
    if (!previewTenantSlug) {
      setPreview({ source: "runtime_code", survey: null, active_db_survey: null, runtime_code_survey: null });
      return;
    }
    const qs = `?tenant_slug=${encodeURIComponent(previewTenantSlug)}`;
    try {
      const res = await request(`/api/admin/survey/preview${qs}`, { cache: "no-store" });
      if (!res.ok) {
        const detail = extractErrorDetail(res.data, res.text ? trimBody(res.text, 500) : "Failed to load preview");
        setApiError({ status: res.status, requestId: res.requestId || (typeof detail.traceId === "string" ? detail.traceId : null), message: detail.message, errors: detail.errors });
        return;
      }
      const source = res.data.source === "active_db" ? "active_db" : "runtime_code";
      setPreview({
        source,
        survey: (res.data.survey as Record<string, unknown>) || null,
        active_db_survey: (res.data.active_db_survey as Record<string, unknown>) || null,
        runtime_code_survey: (res.data.runtime_code_survey as Record<string, unknown>) || null,
      });
      setPreviewSourceView(source);
    } catch (error) {
      setApiError({ message: error instanceof Error ? error.message : "Failed to load preview" });
    }
  };

  useEffect(() => {
    loadState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantSlug]);

  useEffect(() => {
    const scoped = tenantSlug || "";
    if (scoped) {
      setPreviewTenantSlug(scoped);
      return;
    }
    if (!previewTenantSlug && tenants.length > 0) {
      setPreviewTenantSlug(tenants[0].slug);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantSlug, tenants]);

  useEffect(() => {
    loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewTenantSlug]);

  const action = async (url: string, init?: RequestInit, ok = "Done") => {
    const res = await request(url, init);
    if (!res.ok) {
      const detail = extractErrorDetail(res.data, res.text ? trimBody(res.text, 500) : "Action failed");
      setApiError({ status: res.status, requestId: res.requestId || (typeof detail.traceId === "string" ? detail.traceId : null), message: detail.message, errors: detail.errors });
      setMessage(`Failed: ${detail.message}`);
      return false;
    }
    setMessage(ok);
    setApiError(null);
    await loadState();
    await loadPreview();
    return true;
  };

  const initFromCode = async () => action("/api/admin/survey/initialize-from-code", { method: "POST" }, "Initialized survey from code definition.");
  const createDraft = async () => {
    const ok = await action("/api/admin/survey/draft/from-active", { method: "POST" }, "Draft created from active.");
    if (ok) {
      await loadLatestDraft();
      await loadState();
    }
  };
  const saveDraft = async () => {
    if (parseError || schemaError || !parsedJson) {
      setApiError({ message: schemaError || parseError?.message || "Draft definition is invalid and cannot be saved." });
      setMessage("Not saved");
      return;
    }
    setSaveStatus("saving");
    const res = await request("/api/admin/survey/draft/latest", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ definition_json: parsedJson }),
    });
    if (!res.ok) {
      const detail = res.data?.detail as Record<string, unknown> | string | undefined;
      const messageText = typeof detail === "string"
        ? detail
        : String((detail as Record<string, unknown> | undefined)?.message || (res.text ? trimBody(res.text, 500) : "Save failed"));
      const errors = Array.isArray((detail as Record<string, unknown> | undefined)?.errors)
        ? ((detail as Record<string, unknown>).errors as Array<{ path: string; message: string; code?: string }>)
        : [];
      const traceId = typeof detail === "string" ? null : (detail as Record<string, unknown> | undefined)?.trace_id;
      setApiError({
        status: res.status,
        requestId: res.requestId || (typeof traceId === "string" ? traceId : null),
        message: messageText,
        errors,
      });
      setSaveStatus("error");
      setMessage(`Failed: ${messageText}`);
      return;
    }

    const updatedDraft = (res.data?.draft as DefinitionRecord | null) || null;
    if (updatedDraft?.definition_json) {
      const canonical = stableStringify(updatedDraft.definition_json);
      setJsonText(canonical);
      setSavedDraftText(canonical);
    } else {
      setSavedDraftText(jsonText);
    }
    setSaveStatus("saved");
    setApiError(null);
    setMessage("Draft saved.");
    await loadLatestDraft();
    await loadState();
    await loadPreview();
  };
  const validateDraft = async () => {
    if (parseError || schemaError || !parsedJson) return;
    return action("/api/admin/survey/draft/latest/validate", { method: "POST" }, "Draft is valid.");
  };
  const publishDraft = async () => {
    if (parseError || schemaError || !parsedJson) return;
    if (!confirm("Publish latest draft and make it active?")) return;
    await action("/api/admin/survey/draft/latest/publish", { method: "POST" }, "Draft published as active.");
  };
  const rollback = async () => {
    const version = Number(rollbackVersion); if (!Number.isInteger(version)) return setMessage("Select a valid version.");
    if (!confirm(`Rollback active survey to version ${version}?`)) return;
    await action("/api/admin/survey/rollback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version }) }, `Rolled back to v${version}.`);
  };

  const diffText = useMemo(() => {
    const a = stableStringify(active?.definition_json || {});
    const d = stableStringify(parsedDraft || {});
    if (a === d) return "No differences between active and draft.";
    return `Active and draft differ.

Active length: ${a.length}
Draft length: ${d.length}`;
  }, [active, parsedDraft]);

  const draftDirty = jsonText !== savedDraftText;
  const canSubmitDraft = !!draft && !parseError && !schemaError && !!parsedJson && saveStatus !== "saving";
  const selectedPreview = previewSourceView === "runtime_code" ? preview.runtime_code_survey : preview.active_db_survey;
  const activeCounts = countSurvey(active?.definition_json || null);
  const draftCounts = countSurvey(draft?.definition_json || null);
  const runtimeCounts = countSurvey(preview.runtime_code_survey);
  const activeDbCounts = countSurvey(preview.active_db_survey);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Survey administration</h1>
      {debugEnabled ? (
        <div className="mt-3 rounded border border-indigo-200 bg-indigo-50 p-3 text-xs">
          <p className="font-semibold text-indigo-900">Debug panel (last 10 survey admin requests)</p>
          {requestLogs.length === 0 ? <p className="mt-1 text-indigo-700">No requests logged yet.</p> : null}
          <div className="mt-2 space-y-2">
            {requestLogs.map((entry) => (
              <div key={entry.id} className="rounded border border-indigo-200 bg-white p-2">
                <p className="font-mono text-[11px]">[{entry.at}] {entry.method} {entry.url} → {entry.status ?? "ERR"} ({entry.ok ? "ok" : "fail"})</p>
                {entry.requestBody ? <p className="mt-1 text-[11px] text-slate-700">req: {entry.requestBody}</p> : null}
                {entry.responseBody ? <p className="mt-1 text-[11px] text-slate-700">res: {entry.responseBody}</p> : null}
                {entry.error ? <p className="mt-1 text-[11px] text-red-700">error: {entry.error}</p> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <div className="mt-3 grid gap-2 rounded border bg-white p-3 text-sm md:grid-cols-4">
        <div>Active: <b>{active ? `v${active.version}` : "none"}</b></div>
        <div>Latest draft: <b>{draft ? `v${draft.version}` : "none"}</b></div>
        <div>Published versions: <b>{publishedVersions.length}</b></div>
        <div>Preview source: <b>{preview.source === "active_db" ? "Active (DB)" : "Runtime (code)"}</b></div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-sm">
        <button className="rounded border px-3 py-1.5" onClick={initFromCode}>Initialize from code</button>
        <button className="rounded border px-3 py-1.5" onClick={createDraft}>Create draft from active</button>
        <button className="rounded border px-3 py-1.5 disabled:opacity-50" onClick={saveDraft} disabled={!canSubmitDraft || !draftDirty}>Save draft</button>
        <button className="rounded border px-3 py-1.5 disabled:opacity-50" onClick={validateDraft} disabled={!canSubmitDraft}>Validate</button>
        <button className="rounded bg-black px-3 py-1.5 text-white disabled:opacity-50" onClick={publishDraft} disabled={!canSubmitDraft}>Publish</button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-sm">
        {(["overview", "editor", "diff", "preview"] as const).map((t) => <button key={t} className={`rounded px-3 py-1.5 ${tab === t ? "bg-black text-white" : "border"}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {tab === "overview" ? (
        <div className="mt-3 space-y-3 rounded border bg-white p-3 text-sm">
          <div className="grid gap-2 md:grid-cols-2">
            <div>
              <p>Slug: <b>{active?.slug || draft?.slug || "n/a"}</b></p>
              <p>Active version: <b>{active ? `v${active.version}` : "none"}</b></p>
              <p>Active created: {active?.created_at || "n/a"}</p>
              <p>Active sections/questions: {activeCounts.sections} / {activeCounts.questions}</p>
            </div>
            <div>
              <p>Latest draft: <b>{draft ? `v${draft.version}` : "none"}</b></p>
              <p>Draft created: {draft?.created_at || "n/a"}</p>
              <p>Draft updated: {draft?.updated_at || draft?.created_at || "n/a"}</p>
              <p>Draft sections/questions: {draftCounts.sections} / {draftCounts.questions}</p>
            </div>
          </div>
          <div className="rounded border border-slate-200 p-2">
            <p className="font-semibold">Published versions / rollback</p>
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="py-1 pr-3">Version</th>
                    <th className="py-1 pr-3">Active</th>
                    <th className="py-1 pr-3">Created</th>
                    <th className="py-1">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {publishedVersions.map((p) => (
                    <tr key={p.version} className="border-b last:border-b-0">
                      <td className="py-1 pr-3">v{p.version}</td>
                      <td className="py-1 pr-3">{p.is_active ? "yes" : "no"}</td>
                      <td className="py-1 pr-3">{p.created_at || "n/a"}</td>
                      <td className="py-1">
                        <button className="rounded border px-2 py-1 disabled:opacity-50" disabled={p.is_active} onClick={() => { setRollbackVersion(String(p.version)); void action("/api/admin/survey/rollback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version: p.version }) }, `Rolled back to v${p.version}.`); }}>
                          Activate (rollback)
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div>
            <p className="mb-1 font-semibold">Active definition JSON</p>
            <pre className="max-h-64 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">{stableStringify(active?.definition_json || {})}</pre>
          </div>
          <div className="mt-2">Rollback version: <select className="ml-2 rounded border px-2 py-1" value={rollbackVersion} onChange={(e)=>setRollbackVersion(e.target.value)}><option value="">Select</option>{publishedVersions.map((p)=><option key={p.version} value={String(p.version)}>v{p.version}{p.is_active?" (active)":""}</option>)}</select><button className="ml-2 rounded border px-2 py-1" onClick={rollback}>Rollback</button></div>
        </div>
      ) : null}

      {tab === "editor" ? (
        <div className="mt-3">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className={
              saveStatus === "saving"
                ? "text-blue-700"
                : saveStatus === "saved" && !parseError && !schemaError
                  ? "text-emerald-700"
                  : saveStatus === "error"
                    ? "text-red-700"
                    : "text-amber-700"
            }>
              {saveStatus === "saving"
                ? "Saving..."
                : saveStatus === "saved" && !parseError && !schemaError
                  ? "Saved"
                  : saveStatus === "error"
                    ? "Save failed"
                    : "Not saved"}
            </span>
            <span className={!parseError ? "text-emerald-700" : "text-red-700"}>JSON syntax: {!parseError ? "valid" : "invalid"}</span>
            <span className={!schemaError && !parseError ? "text-emerald-700" : "text-red-700"}>Survey schema: {!schemaError && !parseError ? "valid" : "invalid"}</span>
          </div>
          {!draft ? <p className="mb-2 text-xs text-slate-600">No draft exists. Showing active JSON as read-only. Click <b>Create draft from active</b> to begin editing.</p> : null}
          {parseError ? <p className="mb-2 text-xs text-red-700">Invalid JSON: {parseError.message}{parseError.line ? ` (line ${parseError.line}, col ${parseError.column || "?"})` : ""}</p> : null}
          {!parseError && schemaError ? <p className="mb-2 text-xs text-red-700">Invalid survey schema: {schemaError}</p> : null}
          <textarea
            className="h-[500px] w-full rounded border p-3 font-mono text-xs"
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value);
              setMessage("");
              setSaveStatus("dirty");
            }}
            spellCheck={false}
            readOnly={!draft}
          />
        </div>
      ) : null}
      {tab === "diff" ? (
        <div className="mt-3 space-y-3">
          <pre className="rounded bg-slate-900 p-3 text-xs text-slate-100">{diffText}</pre>
          <div className="grid gap-3 lg:grid-cols-2">
            <div>
              <p className="mb-1 text-xs font-semibold">Active (DB)</p>
              <pre className="max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{stableStringify(active?.definition_json || {})}</pre>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold">Draft</p>
              <pre className="max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{stableStringify(parsedDraft || {})}</pre>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div>
              <p className="mb-1 text-xs font-semibold">Runtime (code)</p>
              <pre className="max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{stableStringify(preview.runtime_code_survey || {})}</pre>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold">Active (DB) vs Runtime (code)</p>
              <pre className="max-h-80 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{stableStringify({
                same: stableStringify(preview.active_db_survey || {}) === stableStringify(preview.runtime_code_survey || {}),
                activeLength: stableStringify(preview.active_db_survey || {}).length,
                runtimeLength: stableStringify(preview.runtime_code_survey || {}).length,
              })}</pre>
            </div>
          </div>
        </div>
      ) : null}
      {tab === "preview" ? (
        <div className="mt-3 space-y-3">
          <div className="rounded border bg-white p-3 text-sm">
            <p>Preview source currently used by runtime resolution: <b>{preview.source === "active_db" ? "Active (DB)" : "Runtime (code)"}</b></p>
            <div className="mt-2 flex items-center gap-2 text-xs">
              <span>Preview tenant:</span>
              <select className="rounded border px-2 py-1" value={previewTenantSlug} onChange={(e) => setPreviewTenantSlug(e.target.value)}>
                <option value="">Select tenant</option>
                {tenants.map((t) => <option key={t.slug} value={t.slug}>{t.name} ({t.slug})</option>)}
              </select>
              <span className="text-slate-600">(separate from admin scope)</span>
            </div>
            <div className="mt-2 flex gap-2 text-xs">
              <button className={`rounded px-2 py-1 ${previewSourceView === "active_db" ? "bg-black text-white" : "border"}`} onClick={() => setPreviewSourceView("active_db")}>Show Active (DB)</button>
              <button className={`rounded px-2 py-1 ${previewSourceView === "runtime_code" ? "bg-black text-white" : "border"}`} onClick={() => setPreviewSourceView("runtime_code")}>Show Runtime (code)</button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold">Draft preview</h3>
              {parsedDraft ? <SurveyPreview survey={parsedDraft} /> : <p className="text-sm text-red-700">Preview unavailable: invalid draft JSON.</p>}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">Resolved preview: {previewSourceView === "active_db" ? "Active (DB)" : "Runtime (code)"}</h3>
              <p className="mb-2 text-xs text-slate-600">Sections/questions: {previewSourceView === "active_db" ? `${activeDbCounts.sections}/${activeDbCounts.questions}` : `${runtimeCounts.sections}/${runtimeCounts.questions}`}</p>
              {selectedPreview ? <SurveyPreview survey={selectedPreview as SurveySchema} /> : <p className="text-sm text-slate-500">No preview loaded.</p>}
            </div>
          </div>
        </div>
      ) : null}

      {apiError?.errors && apiError.errors.length > 0 ? <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800"><p className="font-semibold">Validation errors</p><ul className="mt-2 list-disc pl-5">{apiError.errors.map((e,i)=><li key={i}>{e.path}: {e.message}{e.code ? ` (${e.code})` : ""}</li>)}</ul></div> : null}
      {apiError ? <div className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800"><p className="font-semibold">Request failed</p><p>Status: {apiError.status || "n/a"}</p><p>Message: {apiError.message}</p>{apiError.requestId ? <p>Request ID: {apiError.requestId}</p> : null}</div> : null}
      {message ? <p className="mt-4 rounded bg-slate-100 p-3 text-sm">{message}</p> : null}
    </div>
  );
}
