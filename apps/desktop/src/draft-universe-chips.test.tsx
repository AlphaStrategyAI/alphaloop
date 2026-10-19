import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

function makeApi(view: DesktopView): DesktopApi {
  return {
    fetchView: vi.fn(async () => view),
    createDraft: vi.fn(),
    confirmRun: vi.fn(),
    unlockBrief: vi.fn(),
    sendDialogue: vi.fn(),
    pauseResearch: vi.fn(),
    resumeResearch: vi.fn(),
    confirmModification: vi.fn(),
    continueIterate: vi.fn(),
    extendResearch: vi.fn(),
    deleteResearch: vi.fn(),
    resolveConfirm: vi.fn(),
    exportArtifact: vi.fn(async () => "/tmp/export.zip"),
    revealExportInFolder: vi.fn(),
    reverify: vi.fn(),
    reviseMethod: vi.fn(),
    createMethod: vi.fn(),
  };
}

describe("draft universe chips", () => {
  it("renders tickers as nowrap chips", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [],
      settings: {
        thesis: "测试",
        universe: "美国 · 股票",
        universe_symbols: "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池",
        universe_symbol_chips: ["BRK-B", "SPY"],
        max_effective_hours: "3 小时",
        round1_methods: "分段稳健性检验",
        coverage_floor: "至少 5 个标的",
      },
    };
    render(<App api={makeApi(view)} initialView={view} />);
    const chips = screen.getByTestId("universe-symbol-chips");
    expect(chips).toHaveClass("universe-symbol-chips");
    expect(screen.getByText("BRK-B")).toHaveClass("symbol-chip");
    expect(screen.getByText("SPY")).toHaveClass("symbol-chip");
  });
});
