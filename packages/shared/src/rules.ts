import type { AnswersMap, Item, ShowIfRule } from "./types";

function isMissing(value: unknown): boolean {
  return value === undefined || value === null;
}

function isPrimitive(value: unknown): value is string | number | boolean | null {
  return (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  );
}

// Deterministic, fail-closed evaluation:
// - missing answer => false
// - unknown operator => false
// - type mismatch => false (no coercion)
export function isRuleMatch(rule: ShowIfRule, answers: AnswersMap): boolean {
  const actual = answers[rule.trigger_question_code];
  if (isMissing(actual)) return false;

  switch (rule.operator) {
    case "eq": {
      if (!isPrimitive(actual) || Array.isArray(rule.trigger_value)) return false;
      return actual === rule.trigger_value;
    }
    case "neq": {
      if (!isPrimitive(actual) || Array.isArray(rule.trigger_value)) return false;
      return actual !== rule.trigger_value;
    }
    case "in": {
      if (!isPrimitive(actual) || !Array.isArray(rule.trigger_value)) return false;
      return rule.trigger_value.includes(actual);
    }
    case "not_in": {
      if (!isPrimitive(actual) || !Array.isArray(rule.trigger_value)) return false;
      return !rule.trigger_value.includes(actual);
    }
    default:
      return false;
  }
}

export function evaluateShowIf(rules: ShowIfRule[] | undefined, answers: AnswersMap): boolean {
  if (!rules || rules.length === 0) return true;
  return rules.every((rule) => isRuleMatch(rule, answers));
}

export function isItemVisible(item: Item, answers: AnswersMap): boolean {
  return evaluateShowIf(item.rules, answers);
}
