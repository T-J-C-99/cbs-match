import React from "react";
import { renderToString } from "react-dom/server";

const captured: { props?: Record<string, unknown> } = {};

jest.mock("@/components/RequireAuth", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    captured.props = props;
    return null;
  },
}));

describe("match page auth gating", () => {
  test("requires verified + completed survey + complete profile", async () => {
    const MatchPage = (await import("@/app/match/page")).default;
    renderToString(<MatchPage />);
    expect(captured.props?.requireVerified).toBe(true);
    expect(captured.props?.requireCompletedSurvey).toBe(true);
    expect(captured.props?.requireCompleteProfile).toBe(true);
  });
});
