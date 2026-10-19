import {describe, expect, it} from "vitest";

import {railStatusLabel} from "./railStatus";

const briefSettings = {
  thesis: "t",
  universe: "u",
  max_effective_hours: "12h",
  round1_methods: "m",
  coverage_floor: "8y",
};

describe("railStatusLabel", () => {
  it("maps confirm and awaiting views", () => {
    expect(
      railStatusLabel({
        kind: "confirm_run",
        researchId: "r",
        dialogue: [],
        settings: briefSettings,
      }),
    ).toBe("确认开跑");
    expect(
      railStatusLabel({
        kind: "awaiting_confirm",
        researchId: "r",
        version: 1,
        confirmKind: "economic",
        proposed: "a",
        reason: "b",
        effect: "c",
      }),
    ).toBe("等确认");
  });

  it("summarizes research_list from rows and awaiting pin", () => {
    expect(railStatusLabel({kind: "research_list", rows: []})).toBeNull();
    expect(
      railStatusLabel({
        kind: "research_list",
        awaiting: {id: "a", title: "t", status: "awaiting_confirm"},
        rows: [],
      }),
    ).toBe("等确认");
    expect(
      railStatusLabel({
        kind: "research_list",
        rows: [{id: "r", title: "t", status: "confirm_run"}],
      }),
    ).toBe("确认开跑");
  });
});
