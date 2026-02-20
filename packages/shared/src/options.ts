import type { Item, Option, SurveySchema } from "./types";

export function resolveOptions(item: Item, optionSets: SurveySchema["option_sets"]): Option[] {
  if (Array.isArray(item.options)) {
    return item.options;
  }
  if (typeof item.options === "string") {
    return optionSets[item.options] ?? [];
  }
  return [];
}
