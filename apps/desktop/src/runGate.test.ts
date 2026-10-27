import {describe, expect, it} from "vitest";

import {deriveRunGate} from "./runGate";

const open = {
  serverCode: null as string | null,
  resolutionBlocked: false,
  resolutionCode: null,
  marketPending: false,
  sourceChoiceOnCard: true,
  selectedId: "",
  selectedMarket: "US" as const,
  cardMarket: "US" as const,
  unlicensed: false,
  acknowledgedAt: null,
  checkboxAcked: false,
};

describe("deriveRunGate missing source", () => {
  it("reports DATA_SOURCE_UNBOUND when coverage is also short and nothing is selected", () => {
    const gate = deriveRunGate({
      ...open,
      serverCode: "UNIVERSE_TOO_FEW_SYMBOLS",
      selectedId: "",
    });
    expect(gate).toEqual({runnable: false, code: "DATA_SOURCE_UNBOUND"});
  });

  it("keeps the coverage reason after a source is selected", () => {
    const gate = deriveRunGate({
      ...open,
      serverCode: "UNIVERSE_TOO_FEW_SYMBOLS",
      selectedId: "yahoo_daily",
    });
    expect(gate).toEqual({runnable: false, code: "UNIVERSE_TOO_FEW_SYMBOLS"});
  });

  it("does not let a family block get replaced by the missing-source reason", () => {
    const gate = deriveRunGate({
      ...open,
      serverCode: "STRATEGY_FAMILY_NOT_RUNNABLE",
      selectedId: "",
    });
    expect(gate).toEqual({runnable: false, code: "STRATEGY_FAMILY_NOT_RUNNABLE"});
  });
});
