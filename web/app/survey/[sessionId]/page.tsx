"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import {
  computeCompletion,
  nextScreenIndex,
  resolveOptions,
  visibleItemsForScreen,
  visibleScreens,
  type AnswerValue,
  type AnswersMap,
  type Screen,
  type SurveySchema,
} from "@cbs-match/shared";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function SurveyInner() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = Array.isArray(params.sessionId) ? params.sessionId[0] : params.sessionId;

  const [survey, setSurvey] = useState<SurveySchema | null>(null);
  const [answers, setAnswers] = useState<AnswersMap>({});
  const [screenIndex, setScreenIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { fetchWithAuth } = useAuth();

  useEffect(() => {
    if (!sessionId) {
      setError("Invalid session id.");
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        const [surveyRes, sessionRes] = await Promise.all([
          fetchWithAuth(`${API_BASE}/survey/active`),
          fetchWithAuth(`${API_BASE}/sessions/${sessionId}`),
        ]);
        if (!surveyRes.ok || !sessionRes.ok) throw new Error("Failed to load survey");

        const surveyJson = await surveyRes.json();
        const sessionJson = await sessionRes.json();

        const sortedScreens = [...(surveyJson.screens || [])].sort(
          (a: Screen, b: Screen) => a.ordinal - b.ordinal,
        );

        const loadedSurvey: SurveySchema = { ...surveyJson, screens: sortedScreens };
        const loadedAnswers: AnswersMap = (sessionJson.answers || {}) as AnswersMap;
        const vScreens = visibleScreens(loadedSurvey, loadedAnswers) as Screen[];
        const projected = { ...loadedSurvey, screens: vScreens };

        setSurvey(loadedSurvey);
        setAnswers(loadedAnswers);
        setScreenIndex(nextScreenIndex(projected, loadedAnswers));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [sessionId, fetchWithAuth]);

  const currentVisibleScreens = useMemo(() => {
    if (!survey) return [] as Screen[];
    return visibleScreens(survey, answers) as Screen[];
  }, [survey, answers]);

  useEffect(() => {
    if (!survey || currentVisibleScreens.length === 0) return;
    setScreenIndex((idx) => {
      const maxIdx = Math.max(0, currentVisibleScreens.length - 1);
      if (idx > maxIdx) return maxIdx;
      if (idx < 0) return 0;
      return idx;
    });
  }, [survey, currentVisibleScreens]);

  const screen = currentVisibleScreens[screenIndex];

  const currentVisibleItems = useMemo(() => {
    if (!screen) return [] as Screen["items"];
    return visibleItemsForScreen(screen, answers);
  }, [screen, answers]);

  const setAnswer = (code: string, value: AnswerValue | undefined) => {
    setAnswers((prev) => ({ ...prev, [code]: value }));
  };

  const validateScreen = (items: Screen["items"]): string[] => {
    const missing: string[] = [];
    for (const item of items) {
      const q = item.question;
      if (q.is_required && !q.allow_skip) {
        const v = answers[q.code];
        if (v === undefined || v === null || v === "") missing.push(q.code);
      }
    }
    return missing;
  };

  const persistScreen = async (items: Screen["items"]) => {
    const payload = {
      answers: items
        .map((item) => ({ question_code: item.question.code, answer_value: answers[item.question.code] }))
        .filter((a) => a.answer_value !== undefined),
    };

    if (!payload.answers.length) return;

    setSaving(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/sessions/${sessionId}/answers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to save answers");
    } finally {
      setSaving(false);
    }
  };

  const onNext = async () => {
    if (!screen) return;

    const missing = validateScreen(currentVisibleItems);
    if (missing.length) {
      setError("Please answer required questions before continuing.");
      return;
    }

    setError(null);
    await persistScreen(currentVisibleItems);

    if (screenIndex < currentVisibleScreens.length - 1) {
      setScreenIndex((v) => v + 1);
      return;
    }

    const completeRes = await fetchWithAuth(`${API_BASE}/sessions/${sessionId}/complete`, {
      method: "POST",
    });
    if (!completeRes.ok) {
      setError("Could not complete session.");
      return;
    }
    router.push("/done");
  };

  const onBack = async () => {
    if (!screen) return;
    await persistScreen(currentVisibleItems);
    setScreenIndex((v) => Math.max(0, v - 1));
  };

  if (loading) return <div className="mx-auto max-w-3xl p-6">Loading...</div>;
  if (error && !survey) return <div className="mx-auto max-w-3xl p-6 text-red-700">{error}</div>;
  if (!screen || !survey) return <div className="mx-auto max-w-3xl p-6">No visible screens.</div>;

  const projectedSurvey = { ...survey, screens: currentVisibleScreens };
  const completion = computeCompletion(projectedSurvey, answers);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 text-sm text-slate-500">
        Screen {screenIndex + 1} of {currentVisibleScreens.length}
      </div>
      <div className="h-2 w-full overflow-hidden rounded bg-slate-200">
        <div className="h-2 bg-black transition-all" style={{ width: `${completion}%` }} />
      </div>

      <h1 className="mt-6 text-2xl font-semibold">{screen.title}</h1>
      {screen.subtitle && <p className="mt-1 text-slate-600">{screen.subtitle}</p>}

      <div className="mt-6 space-y-6">
        {currentVisibleItems.map((item) => {
          const opts = resolveOptions(item, survey.option_sets);
          const value = answers[item.question.code];

          return (
            <div key={item.question.code} className="rounded border border-slate-200 bg-white p-4">
              <p className="font-medium">
                {item.question.text}
                {item.question.is_required && !item.question.allow_skip ? (
                  <span className="ml-1 text-red-600">*</span>
                ) : null}
              </p>
              <div className="mt-3 space-y-2">
                {opts.map((opt) => {
                  const id = `${item.question.code}-${String(opt.value)}`;
                  return (
                    <label
                      key={id}
                      htmlFor={id}
                      className="flex cursor-pointer items-center gap-3 rounded p-2 hover:bg-slate-50"
                    >
                      <input
                        id={id}
                        type="radio"
                        className="h-4 w-4"
                        name={item.question.code}
                        checked={value === opt.value}
                        onChange={() => setAnswer(item.question.code, opt.value)}
                      />
                      <span>{opt.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {error && <p className="mt-4 rounded bg-red-100 p-3 text-red-700">{error}</p>}

      <div className="mt-8 flex items-center justify-between">
        <button
          className="rounded border border-slate-300 px-4 py-2 text-slate-700 disabled:opacity-50"
          disabled={screenIndex === 0 || saving}
          onClick={onBack}
        >
          Back
        </button>
        <button
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
          disabled={saving}
          onClick={onNext}
        >
          {screenIndex === currentVisibleScreens.length - 1 ? "Complete" : "Next"}
        </button>
      </div>
    </div>
  );
}

export default function SurveyPage() {
  return (
    <RequireAuth>
      <SurveyInner />
    </RequireAuth>
  );
}
