import { describe, expect, it } from "vitest";
import { isItemVisible, isRuleMatch } from "../src/rules";

const baseItem = {
  question: {
    code: "A",
    text: "A",
    response_type: "single_select" as const,
    is_required: true,
    allow_skip: false,
  },
  options: [],
  rules: [],
};

describe("rule evaluation", () => {
  it("eq true and false", () => {
    const rule = { type: "show_if" as const, trigger_question_code: "X", operator: "eq" as const, trigger_value: "ok" };
    expect(isRuleMatch(rule, { X: "ok" })).toBe(true);
    expect(isRuleMatch(rule, { X: "no" })).toBe(false);
  });

  it("neq true and false", () => {
    const rule = { type: "show_if" as const, trigger_question_code: "X", operator: "neq" as const, trigger_value: "ok" };
    expect(isRuleMatch(rule, { X: "no" })).toBe(true);
    expect(isRuleMatch(rule, { X: "ok" })).toBe(false);
  });

  it("in true and false", () => {
    const rule = { type: "show_if" as const, trigger_question_code: "Y", operator: "in" as const, trigger_value: ["yes", "maybe"] };
    expect(isRuleMatch(rule, { Y: "yes" })).toBe(true);
    expect(isRuleMatch(rule, { Y: "no" })).toBe(false);
  });

  it("not_in true and false", () => {
    const rule = { type: "show_if" as const, trigger_question_code: "Y", operator: "not_in" as const, trigger_value: ["no", "skip"] };
    expect(isRuleMatch(rule, { Y: "yes" })).toBe(true);
    expect(isRuleMatch(rule, { Y: "no" })).toBe(false);
  });

  it("missing answer returns false", () => {
    const rule = { type: "show_if" as const, trigger_question_code: "MISSING", operator: "eq" as const, trigger_value: "ok" };
    expect(isRuleMatch(rule, {})).toBe(false);
  });

  it("unknown operator returns false", () => {
    const rule = {
      type: "show_if" as const,
      trigger_question_code: "X",
      operator: "wat" as any,
      trigger_value: "ok",
    };
    expect(isRuleMatch(rule, { X: "ok" })).toBe(false);
  });

  it("item visibility requires all rules", () => {
    const item = {
      ...baseItem,
      rules: [
        { type: "show_if" as const, trigger_question_code: "X", operator: "eq" as const, trigger_value: "ok" },
        { type: "show_if" as const, trigger_question_code: "Y", operator: "not_in" as const, trigger_value: ["no"] },
      ],
    };
    expect(isItemVisible(item, { X: "ok", Y: "yes" })).toBe(true);
    expect(isItemVisible(item, { X: "ok", Y: "no" })).toBe(false);
  });
});
