import { isItemVisible } from "./rules";
import type { AnswersMap, Screen, SurveySchema } from "./types";

export function visibleItemsForScreen(screen: Screen, answers: AnswersMap): Screen["items"] {
  return screen.items.filter((item) => isItemVisible(item, answers));
}

// Backward-compatible alias used by mobile today.
export function visibleItems(screen: Screen, answers: AnswersMap): Screen["items"] {
  return visibleItemsForScreen(screen, answers);
}

export function visibleScreens(schema: SurveySchema, answers: AnswersMap): Screen[] {
  return schema.screens
    .map((screen) => ({ ...screen, items: visibleItemsForScreen(screen, answers) }))
    .filter((screen) => screen.items.length > 0);
}

export function isScreenComplete(screen: Screen, answers: AnswersMap): boolean {
  const items = visibleItemsForScreen(screen, answers);
  return items.every((item) => {
    const q = item.question;
    if (q.allow_skip) return true;
    if (!q.is_required) return true;
    const value = answers[q.code];
    if (value === undefined || value === null) return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "string") return value.trim().length > 0;
    return true;
  });
}

export function computeCompletion(schema: SurveySchema, answers: AnswersMap): number {
  const screens = visibleScreens(schema, answers);
  const total = screens.length;
  if (total === 0) return 0;
  const done = screens.filter((screen) => isScreenComplete(screen, answers)).length;
  return Math.round((done / total) * 100);
}

export function nextScreenIndex(schema: SurveySchema, answers: AnswersMap, fallback = 0): number {
  const idx = schema.screens.findIndex((screen) => !isScreenComplete(screen, answers));
  if (idx === -1) return Math.max(0, schema.screens.length - 1);
  return idx >= 0 ? idx : fallback;
}
