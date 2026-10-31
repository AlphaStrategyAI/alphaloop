import {describe, expect, it} from "vitest";

import {translate} from "./i18n/translate";
import {railStatusKey, railStatusTone} from "./railStatus";

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

  it("uses two-character research labels and run/hold/ok/stop tones", () => {
    const running = railStatusKey({
      kind: "running",
      researchId: "r",
      status: "running",
      version: 1,
      effective: "1h",
      coverage: "ok",
      rounds: [],
    });
    expect(running).toBe("ui.status.railRun");
    expect(railStatusTone(running)).toBe("run");
    expect(translate("zh", "ui.status.railRun")).toBe("运行");
    expect(translate("en", "ui.status.railRun")).toBe("Running");

    const paused = railStatusKey({
      kind: "running",
      researchId: "r",
      status: "paused",
      version: 1,
      effective: "1h",
      coverage: "ok",
      rounds: [],
    });
    expect(paused).toBe("ui.status.railHold");
    expect(railStatusTone(paused)).toBe("hold");
    expect(translate("zh", "ui.status.railHold")).toBe("暂停");
    expect(translate("en", "ui.status.railHold")).toBe("Paused");

    const passed = railStatusKey({
      kind: "completed",
      researchId: "r",
      status: "completed",
      title: "t",
      selectedRoundId: "round",
      selectedMethodId: "m",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
    });
    expect(passed).toBe("ui.status.railOk");
    expect(railStatusTone(passed)).toBe("ok");
    expect(translate("en", "ui.status.railOk")).toBe("Done");

    const failed = railStatusKey({
      kind: "completed",
      researchId: "r",
      status: "ended",
      title: "t",
      selectedRoundId: "round",
      selectedMethodId: "m",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
    });
    expect(failed).toBe("ui.status.railStop");
    expect(railStatusTone(failed)).toBe("stop");
    expect(translate("zh", "ui.status.railStop")).toBe("完成");
    expect(translate("en", "ui.status.railStop")).toBe("Done");
    expect(railStatusTone("ui.status.confirmRun")).toBeNull();
  });
});
