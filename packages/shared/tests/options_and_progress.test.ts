import { describe, expect, it } from "vitest";
import {
  computeCompletion,
  nextScreenIndex,
  resolveOptions,
  visibleItemsForScreen,
  visibleScreens,
} from "../src";

const schema = {
  survey: { slug: "s", version: 1, name: "n", status: "draft" },
  option_sets: {
    basic: [{ value: "a", label: "A" }],
  },
  screens: [
    {
      key: "one",
      ordinal: 1,
      title: "One",
      items: [
        {
          question: { code: "Q1", text: "Q1", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: "basic",
          rules: [],
        },
      ],
    },
    {
      key: "two",
      ordinal: 2,
      title: "Two",
      items: [
        {
          question: { code: "Q2", text: "Q2", response_type: "single_select" as const, is_required: true, allow_skip: false },
          options: [{ value: "b", label: "B" }],
          rules: [{ type: "show_if" as const, trigger_question_code: "Q1", operator: "eq" as const, trigger_value: "a" }],
        },
      ],
    },
  ],
};

describe("option resolver, visibility, and completion", () => {
  it("resolves option set references", () => {
    const opts = resolveOptions(schema.screens[0].items[0], schema.option_sets);
    expect(opts[0].value).toBe("a");
  });

  it("computes visible screens and completion", () => {
    expect(visibleScreens(schema as never, {}).length).toBe(1);
    expect(visibleItemsForScreen(schema.screens[1] as never, {}).length).toBe(0);

    expect(computeCompletion(schema as never, {})).toBe(0);
    expect(nextScreenIndex(schema as never, {})).toBe(0);

    const ans = { Q1: "a" };
    expect(visibleScreens(schema as never, ans).length).toBe(2);
    expect(computeCompletion(schema as never, ans)).toBe(50);
    expect(nextScreenIndex(schema as never, ans)).toBe(1);

    const complete = { Q1: "a", Q2: "b" };
    expect(computeCompletion(schema as never, complete)).toBe(100);
  });
});
