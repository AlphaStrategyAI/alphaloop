import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import type {DesktopApi, DesktopView} from "./contracts";
import {DraftScreen} from "./screens/ConfirmRunScreen";
import {I18nProvider} from "./i18n/I18nProvider";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const METHODS =
  "subperiod robustness check, out-of-sample stability, concentration, turnover cost";

afterEach(() => cleanup());

function api(): DesktopApi & {sendDialogue: ReturnType<typeof vi.fn>} {
  return {
    fetchView: vi.fn(),
    createDraft: vi.fn(),
    confirmRun: vi.fn(),
    setResearchSymbol: vi.fn(),
    answerSymbolAsk: vi.fn(),
    useHintedSymbol: vi.fn(),
    revertSymbolAsk: vi.fn(),
    removeMarketSide: vi.fn(),
    dismissMismatchedSymbol: vi.fn(),
    chooseDefaultMarket: vi.fn(),
    setPriceSource: vi.fn(),
    unlockBrief: vi.fn(),
    sendDialogue: vi.fn(async () => undefined),
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
  } as DesktopApi & {sendDialogue: ReturnType<typeof vi.fn>};
}

const view: Extract<DesktopView, {kind: "draft"}> = {
  kind: "draft",
  researchId: "r-input",
  dialogue: [],
  settings: {
    thesis: "",
    universe: "",
    max_effective_hours: "",
    round1_methods: "",
    coverage_floor: "",
  },
};

describe("chat intake", () => {
  it("wraps a long English method sentence and still submits on Enter", () => {
    const desktop = api();
    render(
      <I18nProvider initial={EN}>
        <DraftScreen api={desktop} view={view} />
      </I18nProvider>,
    );
    const input = screen.getByTestId("dialogue-input");
    expect(input.tagName).toBe("TEXTAREA");
    expect(input).toHaveClass("dialogue-input");
    fireEvent.change(input, {target: {value: METHODS}});
    expect((input as HTMLTextAreaElement).value).toBe(METHODS);
    fireEvent.keyDown(input, {key: "Enter"});
    expect(desktop.sendDialogue).toHaveBeenCalledWith("r-input", METHODS);
    expect((input as HTMLTextAreaElement).value).not.toContain("\n");
  });
});
