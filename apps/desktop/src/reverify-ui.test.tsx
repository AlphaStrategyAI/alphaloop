import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

function makeApi(view: DesktopView): DesktopApi {
  return {
    fetchView: vi.fn(async () => view),
    createDraft: vi.fn(),
    confirmRun: vi.fn(),
    setResearchSymbol: vi.fn(async () => undefined),
  answerSymbolAsk: vi.fn(async () => undefined),
  useHintedSymbol: vi.fn(async () => undefined),
  revertSymbolAsk: vi.fn(async () => undefined),
  removeMarketSide: vi.fn(async () => undefined),
  dismissMismatchedSymbol: vi.fn(async () => undefined),
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

describe("reverify controls", () => {
  it("keeps method when switching round if still available", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "t",
      selectedRoundId: "r1",
      selectedMethodId: "overfit.walk",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: false,
      },
      reverifyOptions: {
        rounds: [
          {
            roundId: "r1",
            roundLabel: "第 1 轮",
            methods: [
              {methodId: "scorecard.market", methodLabel: "市场计分卡"},
              {methodId: "overfit.walk", methodLabel: "分段稳健性检验"},
            ],
          },
          {
            roundId: "r2",
            roundLabel: "第 2 轮",
            methods: [{methodId: "overfit.walk", methodLabel: "分段稳健性检验"}],
          },
        ],
      },
    };
    render(<App api={makeApi(view)} initialView={view} initialRoute="#/research/r-1" />);
    const methodSelect = screen.getByTestId("reverify-method-select") as HTMLSelectElement;
    expect(methodSelect.value).toBe("overfit.walk");
    fireEvent.change(screen.getByTestId("reverify-round-select"), {target: {value: "r2"}});
    expect((screen.getByTestId("reverify-method-select") as HTMLSelectElement).value).toBe(
      "overfit.walk",
    );
  });

  it("uses the existing fail token when reverify did not pass", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "t",
      selectedRoundId: "r1",
      selectedMethodId: "overfit.walk",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: false,
        pitExecutedAndPassed: true,
      },
      lastReverification: {
        roundId: "r1",
        methodId: "overfit.walk",
        methodLabel: "分段稳健性检验",
        passed: false,
        createdAt: "2026-10-19T00:00:00+00:00",
        userMessage: "「分段稳健性检验」重验未通过。",
      },
    };
    render(<App api={makeApi(view)} initialView={view} initialRoute="#/research/r-1" />);
    const result = screen.getByTestId("reverify-result");
    expect(result).toHaveTextContent("「分段稳健性检验」重验未通过。");
    expect(result).toHaveClass("reverify-result--fail");
  });
});
