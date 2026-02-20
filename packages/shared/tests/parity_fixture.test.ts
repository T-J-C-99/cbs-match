import { describe, expect, it } from "vitest";
import {
  computeCompletion,
  isRuleMatch,
  nextScreenIndex,
  resolveOptions,
  visibleItemsForScreen,
  visibleScreens,
} from "../src";

const fixture = {
  survey: { slug: "fixture", version: 1, name: "Fixture", status: "active" },
  option_sets: {
    likert_1_5_agree: [
      { value: 1, label: "Strongly disagree" },
      { value: 5, label: "Strongly agree" },
    ],
  },
  screens: [
    {
      key: "intro",
      ordinal: 1,
      title: "Intro",
      items: [
        {
          question: { code: "CONSENT", text: "Consent", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: [
            { value: "yes", label: "Yes" },
            { value: "no", label: "No" },
          ],
          rules: [],
        },
      ],
    },
    {
      key: "details",
      ordinal: 2,
      title: "Details",
      items: [
        {
          question: { code: "EQ_Q", text: "Eq", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: "likert_1_5_agree",
          rules: [{ type: "show_if" as const, trigger_question_code: "CONSENT", operator: "eq" as const, trigger_value: "yes" }],
        },
        {
          question: { code: "NEQ_Q", text: "Neq", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: "likert_1_5_agree",
          rules: [{ type: "show_if" as const, trigger_question_code: "CONSENT", operator: "neq" as const, trigger_value: "no" }],
        },
        {
          question: { code: "IN_Q", text: "In", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: "likert_1_5_agree",
          rules: [{ type: "show_if" as const, trigger_question_code: "CONSENT", operator: "in" as const, trigger_value: ["yes", "maybe"] }],
        },
        {
          question: { code: "NOT_IN_Q", text: "Not In", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: "likert_1_5_agree",
          rules: [{ type: "show_if" as const, trigger_question_code: "CONSENT", operator: "not_in" as const, trigger_value: ["no"] }],
        },
      ],
    },
  ],
};

describe("parity fixture for visibility and progress", () => {
  it("produces deterministic visibility, completion, and next index", () => {
    const emptyAnswers = {};
    const consentYes = { CONSENT: "yes" };

    expect(resolveOptions(fixture.screens[1].items[0] as never, fixture.option_sets).length).toBe(2);

    expect(visibleScreens(fixture as never, emptyAnswers).map((s) => s.key)).toEqual(["intro"]);
    expect(visibleItemsForScreen(fixture.screens[1] as never, emptyAnswers).map((i) => i.question.code)).toEqual([]);
    expect(computeCompletion(fixture as never, emptyAnswers)).toBe(0);
    expect(nextScreenIndex(fixture as never, emptyAnswers)).toBe(0);

    expect(visibleScreens(fixture as never, consentYes).map((s) => s.key)).toEqual(["intro", "details"]);
    expect(visibleItemsForScreen(fixture.screens[1] as never, consentYes).map((i) => i.question.code)).toEqual([
      "EQ_Q",
      "NEQ_Q",
      "IN_Q",
      "NOT_IN_Q",
    ]);
    expect(computeCompletion(fixture as never, consentYes)).toBe(50);
    expect(nextScreenIndex(fixture as never, consentYes)).toBe(1);
  });

  it("fails closed on unknown operator via casted rule", () => {
    const rule = {
      type: "show_if" as const,
      trigger_question_code: "CONSENT",
      operator: "unknown" as any,
      trigger_value: "yes",
    };
    expect(isRuleMatch(rule, { CONSENT: "yes" } as any)).toBe(false);
  });
});
