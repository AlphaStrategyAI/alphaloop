import {describe, expect, it} from "vitest";

import type {DesktopView} from "./contracts";
import {shouldTriggerRunStartRitual} from "./runStartRitual";

const settings = {
  thesis: "t",
  universe: "u",
  max_effective_hours: "12h",
  round1_methods: "m",
  coverage_floor: "c",
};

describe("shouldTriggerRunStartRitual", () => {
  it("triggers on confirm_run → running for same research", () => {
    const prev: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      settings,
    };
    const next: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "0h / 12h",
      coverage: "ok",
      rounds: [],
    };
    expect(shouldTriggerRunStartRitual(prev, next)).toBe(true);
  });

  it("does not trigger for draft → running or different ids", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-2",
      status: "running",
      version: 1,
      effective: "1h",
      coverage: "ok",
      rounds: [],
    };
    expect(
      shouldTriggerRunStartRitual(
        {kind: "draft", researchId: "r-1", dialogue: [], settings},
        running,
      ),
    ).toBe(false);
    expect(
      shouldTriggerRunStartRitual(
        {kind: "confirm_run", researchId: "r-1", dialogue: [], settings},
        {...running, researchId: "r-9"},
      ),
    ).toBe(false);
  });
});
