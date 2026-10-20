import {describe, expect, it} from "vitest";

import {translate} from "./i18n/translate";
import {railStatusKey} from "./railStatus";

const briefSettings = {
  thesis: "t",
  universe: "u",
  max_effective_hours: "12h",
  round1_methods: "m",
  coverage_floor: "8y",
};

describe("railStatusKey", () => {
  it("maps confirm and awaiting views", () => {
    expect(
      railStatusKey({
        kind: "confirm_run",
        researchId: "r",
        dialogue: [],
        settings: briefSettings,
      }),
    ).toBe("ui.status.confirmRun");
    expect(translate("zh", "ui.status.confirmRun")).toBe("确认开跑");
    expect(
      railStatusKey({
        kind: "awaiting_confirm",
        researchId: "r",
        version: 1,
        confirmKind: "economic",
        proposed: "a",
        reason: "b",
        effect: "c",
      }),
    ).toBe("ui.status.awaitingShort");
  });

  it("summarizes research_list from rows and awaiting pin", () => {
    expect(railStatusKey({kind: "research_list", rows: []})).toBeNull();
    expect(
      railStatusKey({
        kind: "research_list",
        awaiting: {id: "a", title: "t", status: "awaiting_confirm"},
        rows: [],
      }),
    ).toBe("ui.status.awaitingShort");
    expect(
      railStatusKey({
        kind: "research_list",
        rows: [{id: "r", title: "t", status: "confirm_run"}],
      }),
    ).toBe("ui.status.confirmRun");
  });
});
