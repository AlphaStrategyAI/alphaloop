import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView, PriceSourceChoice} from "./contracts";
import {formatResearchTimestamp} from "./format";
import {I18nProvider} from "./i18n/I18nProvider";
import {CompletedScreen} from "./screens/CompletedScreen";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};

afterEach(() => cleanup());

function api(): DesktopApi {
  return {
    fetchView: vi.fn(),
    createDraft: vi.fn(),
    confirmRun: vi.fn(async () => undefined),
    setResearchSymbol: vi.fn(async () => undefined),
    answerSymbolAsk: vi.fn(async () => undefined),
    useHintedSymbol: vi.fn(async () => undefined),
    revertSymbolAsk: vi.fn(async () => undefined),
    removeMarketSide: vi.fn(async () => undefined),
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

const confirmView: Extract<DesktopView, {kind: "confirm_run"}> = {
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
    offeredDataSourceId: "yahoo_daily",
    offeredDataSource: "雅虎日线",
    unlicensedAcknowledgedAt: null,
    unlicensedAcknowledgementRequired: false,
    priceSources: [
      {id: "yahoo_daily", label: "雅虎日线", unlicensed: true, acknowledgedAt: null},
    ],
  },
};

const ACK_AT = "2026-10-23T17:57:51.504418+00:00";

function sources(acknowledgedAt: string | null): PriceSourceChoice[] {
  return [{id: "yahoo_daily", label: "雅虎日线", unlicensed: true, acknowledgedAt}];
}

describe("confirm source presentation", () => {
  it("formats the acknowledgement in local time and updates the source line", () => {
    const ackedView: Extract<DesktopView, {kind: "confirm_run"}> = {
      ...confirmView,
      symbolSelection: {
        ...confirmView.symbolSelection!,
        dataSourcePending: true,
        priceSources: sources(ACK_AT),
      },
    };
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api()} view={ackedView} />
      </I18nProvider>,
    );
    expect(screen.queryByTestId("unlicensed-ack-done")).toBeNull();
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    const done = screen.getByTestId("unlicensed-ack-done");
    expect(done.textContent).toContain(formatResearchTimestamp(ACK_AT));
    expect(done.textContent).not.toContain("T17:57:51");
    expect(screen.getByTestId("confirm-data-meta").textContent).toContain("Yahoo daily");
    expect(screen.getByTestId("confirm-data-meta").textContent).not.toContain("Not selected");
    expect(screen.getByTestId("unlicensed-notice")).toBeInTheDocument();
  });

  it("hides the unlicensed notice when a licensed local file is selected", () => {
    const licensed: Extract<DesktopView, {kind: "confirm_run"}> = {
      ...confirmView,
      symbolSelection: {
        ...confirmView.symbolSelection!,
        dataSource: "Desk CSV",
        dataSourceId: "local-file-desk",
        dataSourcePending: false,
        priceSources: [
          {id: "local-file-desk", label: "Desk CSV", unlicensed: false, acknowledgedAt: null},
          {id: "yahoo_daily", label: "雅虎日线", unlicensed: true, acknowledgedAt: null},
        ],
      },
    };
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api()} view={licensed} />
      </I18nProvider>,
    );
    expect(screen.queryByTestId("unlicensed-notice")).toBeNull();
    expect(screen.getByTestId("confirm-data-meta").textContent).toContain("Desk CSV");
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    expect(screen.getByTestId("unlicensed-notice")).toBeInTheDocument();
  });
});

describe("unlicensed tag", () => {
  it("renders Unlicensed in English and 未经许可 in Chinese", () => {
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api()} view={confirmView} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("unlicensed-tag").textContent).toBe("Unlicensed");
    unmount();
    render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={api()} view={confirmView} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("unlicensed-tag").textContent).toBe("未经许可");
  });
});

describe("unlicensed confirm card", () => {
  it("does not preselect Yahoo and blocks Run until the personal-research box is ticked", () => {
    const desktop = api();
    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={desktop} view={confirmView} />
      </I18nProvider>,
    );
    const choice = screen.getByTestId("price-source-yahoo_daily") as HTMLInputElement;
    expect(choice.checked).toBe(false);
    expect(screen.queryByTestId("unlicensed-ack")).toBeNull();
    const run = screen.getByTestId("confirm-run-start") as HTMLButtonElement;
    expect(run.disabled).toBe(true);

    fireEvent.click(choice);
    const ack = screen.getByTestId("unlicensed-ack") as HTMLInputElement;
    expect(ack.checked).toBe(false);
    expect(run.disabled).toBe(true);
    expect(screen.getByTestId("unlicensed-ack-row").textContent).toMatch(/personal research/i);

    fireEvent.click(ack);
    expect(run.disabled).toBe(false);
    fireEvent.click(run);
    expect(desktop.confirmRun).toHaveBeenCalledWith("r-spy", {
      dataSourceId: "yahoo_daily",
      unlicensedAcknowledged: true,
    });
  });
});

const completed = {
  kind: "completed" as const,
  researchId: "r-spy",
  status: "completed" as const,
  title: "SPY",
  selectedRoundId: "r1",
  selectedMethodId: "m1",
  eligibility: {
    allMethodsPassed: false,
    noPendingConfirm: true,
    reverifiesPassed: true,
    pitExecutedAndPassed: true,
  },
  effective: "0.00 小时",
  effectiveSeconds: 7,
  remaining: "12.00 小时",
  remainingSeconds: 12 * 3600 - 7,
  stopReason: "round_cap" as const,
  trialBudget: {used: 5, budget: 5, remaining: 0},
};

describe("stop reason and sub-hour duration", () => {
  it("names the round cap in English and does not present 7 seconds as 0.00 hours", () => {
    render(
      <I18nProvider initial={EN}>
        <CompletedScreen api={api()} view={completed} />
      </I18nProvider>,
    );
    const reason = screen.getByTestId("stop-reason");
    expect(reason.textContent).toMatch(/round cap was reached \(5\/5\)/i);
    expect(reason.textContent).toMatch(/time budget was not used up/i);
    const header = screen.getByTestId("completed-workbench-header");
    expect(header.textContent).toContain("7 seconds");
    expect(header.textContent).not.toContain("0.00 hours");
  });

  it("names the round cap in Chinese and shows seconds", () => {
    render(
      <I18nProvider initial={ZH}>
        <CompletedScreen api={api()} view={completed} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("stop-reason").textContent).toContain("轮次上限已到（5/5 轮）");
    expect(screen.getByTestId("completed-workbench-header").textContent).toContain("7 秒");
    expect(screen.getByTestId("completed-workbench-header").textContent).not.toContain("0.00 小时");
  });
});
