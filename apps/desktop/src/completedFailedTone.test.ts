import {describe, expect, it} from "vitest";

import {completedShowsFailedTone, viewContentFailedTone} from "./completedFailedTone";
import type {DesktopView} from "./contracts";

const baseCompleted: Extract<DesktopView, {kind: "completed"}> = {
  kind: "completed",
  researchId: "r-1",
  status: "completed",
  title: "t",
  selectedRoundId: "r1",
  selectedMethodId: "m1",
  eligibility: {
    allMethodsPassed: true,
    noPendingConfirm: true,
    reverifiesPassed: true,
    pitExecutedAndPassed: true,
  },
};

describe("completedFailedTone", () => {
  it("marks gate-failed completed views as failed tone", () => {
    const view = {
      ...baseCompleted,
      exportKind: "research_record_only" as const,
      eligibility: {
        ...baseCompleted.eligibility,
        pitExecutedAndPassed: false,
      },
    };
    expect(completedShowsFailedTone(view)).toBe(true);
    expect(viewContentFailedTone(view)).toBe(true);
  });

  it("marks export-ready completed as success tone", () => {
    expect(completedShowsFailedTone(baseCompleted)).toBe(false);
    expect(viewContentFailedTone(baseCompleted)).toBe(false);
  });
});
