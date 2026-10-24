import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {bindDesktopApi} from "./api-bind";
import {confirmRunEnginePayload} from "./confirmRunCommand";
import {ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};

const UNBOUND = JSON.stringify({
  error: "这项研究还没有可用的数据来源。",
  code: "DATA_SOURCE_UNBOUND",
  params: {},
  detail: null,
});

afterEach(() => cleanup());

const view: Extract<DesktopView, {kind: "confirm_run"}> = {
  kind: "confirm_run",
  researchId: "r-spy",
  dialogue: [],
  settings: {
    thesis: "mean reversion",
    universe: "US · equities",
    max_effective_hours: "12 小时",
    round1_methods: "cost",
    coverage_floor: "1 name",
  },
  symbolSelection: {
    count: 1,
    listName: "用户指定标的",
    listVersion: "user",
    symbols: ["SPY"],
    source: "user_override",
    dataStart: "2014-10-26",
    dataEnd: "2026-10-23",
    dataCutoff: "2026-10-23",
    dataSource: "待选择",
    dataSourceId: null,
    dataSourcePending: true,
    priceSources: [
      {id: "yahoo_daily", label: "雅虎日线", unlicensed: true, acknowledgedAt: null},
    ],
  },
};

function shell(confirmRun: DesktopApi["confirmRun"]): DesktopApi {
  return {
    fetchView: vi.fn(),
    createDraft: vi.fn(),
    confirmRun,
    setResearchSymbol: vi.fn(async () => undefined),
    answerSymbolAsk: vi.fn(async () => undefined),
    useHintedSymbol: vi.fn(async () => undefined),
    revertSymbolAsk: vi.fn(async () => undefined),
    removeMarketSide: vi.fn(async () => undefined),
    dismissMismatchedSymbol: vi.fn(async () => undefined),
    chooseDefaultMarket: vi.fn(async () => undefined),
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

async function tickYahooAndRun() {
  fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
  fireEvent.click(screen.getByTestId("unlicensed-ack"));
  fireEvent.click(screen.getByTestId("confirm-run-start"));
  await Promise.resolve();
}

describe("confirm run call chain", () => {
  it("sends the chosen source and acknowledgement through api-bind to the engine payload", async () => {
    const payloads: unknown[] = [];
    const raw = shell(async (researchId, options) => {
      payloads.push(confirmRunEnginePayload(researchId, options));
    });
    const bound = bindDesktopApi(raw, {
      refresh: async () => undefined,
      onError: () => undefined,
    });
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={bound} view={view} />
      </I18nProvider>,
    );

    await tickYahooAndRun();

    expect(payloads).toEqual([
      {
        type: "confirm_run",
        research_id: "r-spy",
        data_source_id: "yahoo_daily",
        unlicensed_acknowledged: true,
      },
    ]);
  });

  it("shows a DATA_SOURCE_UNBOUND engine error in English and Chinese", async () => {
    const raw = shell(async () => {
      throw new Error(UNBOUND);
    });
    const onError = vi.fn();
    const bound = bindDesktopApi(raw, {refresh: async () => undefined, onError});
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={bound} view={view} />
      </I18nProvider>,
    );
    await tickYahooAndRun();
    await waitFor(() => {
      expect(screen.getByTestId("confirm-run-error").textContent).toContain(
        "This research does not have a data source yet.",
      );
    });
    expect(onError).toHaveBeenCalledWith(UNBOUND);
    unmount();

    render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={bound} view={view} />
      </I18nProvider>,
    );
    await tickYahooAndRun();
    await waitFor(() => {
      expect(screen.getByTestId("confirm-run-error").textContent).toContain(
        "这项研究还没有可用的数据来源。",
      );
    });
  });
});
