import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import type {DesktopApi, DesktopView} from "./contracts";
import {ConfirmRunCard} from "./screens/ConfirmRunScreen";
import {I18nProvider} from "./i18n/I18nProvider";
import {EngineFailureText} from "./i18n/engineFailure";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};
const CJK = /[\u4e00-\u9fff]/;

afterEach(() => cleanup());

function api(): DesktopApi {
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
  } as DesktopApi;
}

function view(): Extract<DesktopView, {kind: "confirm_run"}> {
  return {
    kind: "confirm_run",
    researchId: "r-few",
    dialogue: [],
    settings: {
      thesis: "Mean reversion on AAPL, a US stock, using daily prices.",
      universe: "美股 · 股票",
      max_effective_hours: "30 分钟",
      round1_methods: "分段稳健性检验 · 样本外稳定 · 集中度 · 换手成本",
      coverage_floor: "至少 25 个标的、10 年数据，缺失不超过 5%",
    },
    market: "US",
    runGate: {
      runnable: false,
      code: "UNIVERSE_TOO_FEW_SYMBOLS",
      params: {count: 1, minimum: 25},
    },
    symbolSelection: {
      count: 1,
      listName: "用户指定标的",
      listVersion: "user",
      symbols: ["AAPL"],
      source: "user_override",
      dataStart: "2014-10-29",
      dataEnd: "2026-10-26",
      dataCutoff: "2026-10-26",
      dataSource: "雅虎日线",
      dataSourceId: "yahoo_daily",
      dataSourcePending: false,
      priceSources: [
        {
          id: "yahoo_daily",
          label: "雅虎日线",
          unlicensed: true,
          market: "US",
          acknowledgedAt: "2026-10-27T07:06:00+00:00",
        },
      ],
    },
  };
}

const RAW = JSON.stringify({
  error: "当前仅 1 个标的，低于最低覆盖要求的 25 个。请调低覆盖底线或增加标的后再开跑。",
  code: "UNIVERSE_TOO_FEW_SYMBOLS",
  params: {count: 1, minimum: 25},
  detail: null,
});

describe("coverage floor versus the named universe", () => {
  it("disables Run in English with the same language in the banner", () => {
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api()} view={view()} />
        <EngineFailureText raw={RAW} />
      </I18nProvider>,
    );
    const run = screen.getByTestId("confirm-run-start");
    expect(run).toBeDisabled();
    expect(run).toHaveAttribute("data-run-blocked", "coverage");
    const reason = screen.getByTestId("confirm-run-blocked-reason").textContent ?? "";
    expect(reason).toMatch(/1 name/i);
    expect(reason).toContain("25");
    expect(reason).not.toMatch(CJK);
    const summary = screen.getByTestId("engine-failure-summary").textContent ?? "";
    expect(summary).toMatch(/1 name/i);
    expect(summary).toContain("25");
    expect(summary).not.toMatch(/Something went wrong/);
    expect(summary).not.toMatch(CJK);
    const detail = screen.queryByTestId("engine-failure-detail")?.textContent ?? "";
    expect(detail).not.toMatch(CJK);
    expect(detail).not.toContain("当前仅");
  });

  it("disables Run in Chinese with a Chinese reason and banner", () => {
    render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={api()} view={view()} />
        <EngineFailureText raw={RAW} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    const reason = screen.getByTestId("confirm-run-blocked-reason").textContent ?? "";
    expect(reason).toContain("当前仅 1 个标的");
    expect(reason).toContain("25");
    const summary = screen.getByTestId("engine-failure-summary").textContent ?? "";
    expect(summary).toContain("当前仅 1 个标的");
    expect(summary).not.toContain("UNIVERSE_TOO_FEW_SYMBOLS");
    expect(summary).not.toMatch(/Something went wrong/);
  });
});
