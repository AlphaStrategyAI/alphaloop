import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import type {DesktopApi, DesktopView} from "../contracts";
import {RunningScreen} from "../screens/RunningScreen";
import {ConfirmRunCard} from "../screens/ConfirmRunScreen";
import {I18nProvider} from "./I18nProvider";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const CJK = /[\u4e00-\u9fff]/;

afterEach(() => cleanup());

function api(): DesktopApi {
  return {
    fetchView: vi.fn(),
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

describe("English run page", () => {
  it("does not leave the coverage floor or decimal hours in Chinese", () => {
    const confirm: DesktopView = {
      kind: "confirm_run",
      researchId: "r-en",
      dialogue: [],
      chatEnabled: false,
      settings: {
        thesis: "Mean reversion on AAPL",
        universe: "美股 · 股票",
        max_effective_hours: "0.0833333 小时",
        round1_methods: "分段稳健性检验",
        coverage_floor: "至少 1 个标的、10 年、缺失不超过 5%",
      },
    };
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api()} view={confirm} />
      </I18nProvider>,
    );
    const card = screen.getByTestId("confirm-run-card");
    expect(card).toHaveTextContent("Confirm to run");
    expect(card).toHaveTextContent("5 min");
    expect(card).toHaveTextContent("At least 1 name, 10 years of data, missing no more than 5%");
    expect(card.textContent).not.toMatch(CJK);
    expect(card.textContent).not.toMatch(/0\.00|0\.0833333/);
    unmount();

    const running: DesktopView = {
      kind: "running",
      researchId: "r-en",
      status: "running",
      version: 1,
      effective: "0.00 小时",
      remaining: "4h",
      coverage: "至少 1 个标的、10 年数据，缺失不超过 5%",
      rounds: [],
    };
    render(
      <I18nProvider initial={EN}>
        <RunningScreen api={api()} view={running} modification="" onModificationChange={() => undefined} />
      </I18nProvider>,
    );
    const page = screen.getByTestId("running-screen");
    expect(page).toHaveTextContent("0 seconds / 4 h");
    expect(page).toHaveTextContent("At least 1 name, 10 years of data, missing no more than 5%");
    expect(page.textContent).not.toMatch(CJK);
    expect(page.textContent).not.toMatch(/0\.00 hours|0\.0833333/);
  });
});
