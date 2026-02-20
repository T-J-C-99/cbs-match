"use client";

import { useMemo, useState } from "react";
import {
  visibleItemsForScreen,
  visibleScreens,
  resolveOptions,
  type AnswersMap,
  type Screen,
  type SurveySchema,
} from "@cbs-match/shared";

export default function SurveyPreview({ survey }: { survey: SurveySchema }) {
  const [answers, setAnswers] = useState<AnswersMap>({});

  const screens = useMemo(() => visibleScreens(survey, answers) as Screen[], [survey, answers]);

  return (
    <div className="space-y-6">
      {screens.map((screen) => {
        const items = visibleItemsForScreen(screen, answers);
        return (
          <div key={screen.key} className="rounded border border-slate-200 bg-white p-4">
            <h3 className="text-lg font-semibold">{screen.title}</h3>
            {screen.subtitle ? <p className="mt-1 text-sm text-slate-600">{screen.subtitle}</p> : null}
            <div className="mt-4 space-y-4">
              {items.map((item) => {
                const code = item.question.code;
                const value = answers[code];
                const opts = resolveOptions(item, survey.option_sets);
                return (
                  <div key={code} className="rounded border border-slate-100 p-3">
                    <p className="font-medium">{item.question.text}</p>
                    <div className="mt-2 space-y-2">
                      {opts.map((opt) => {
                        const id = `${code}-${String(opt.value)}`;
                        return (
                          <label key={id} htmlFor={id} className="flex items-center gap-2 text-sm text-slate-700">
                            <input
                              id={id}
                              type="radio"
                              name={code}
                              checked={value === opt.value}
                              onChange={() => setAnswers((prev) => ({ ...prev, [code]: opt.value }))}
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
          </div>
        );
      })}
      {screens.length === 0 ? <p className="text-sm text-slate-500">No visible preview screens.</p> : null}
    </div>
  );
}
