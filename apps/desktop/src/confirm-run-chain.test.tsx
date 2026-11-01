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
    setPriceSource: vi.fn(async () => undefined),
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

    await waitFor(() => expect(payloads).toEqual([
      {
        type: "confirm_run",
        research_id: "r-spy",
        data_source_id: "yahoo_daily",
        unlicensed_acknowledged: true,
      },
    ]));
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

  it("renders the proposal on the confirm card and binds it to confirm_run", async () => {
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
        <ConfirmRunCard
          api={bound}
          view={{
            ...view,
            revision: 4,
            proposal: {
              proposalId: "p-card",
              baseRevision: 3,
              kind: "interpret_brief",
              intent: "provide",
              status: "open",
              nextStep: "",
              originalThesis: "buy cheap stocks",
              executableRule: "daily mean reversion",
              executableRuleSource: "system_suggested",
              meaningNote: "Mean reversion changes the original wording.",
              quotes: [{ref: "q0", text: "buy cheap stocks"}],
              changes: [{field: "max_effective_hours", source: "user_specified", text: "2", quoteRef: "q0"}],
              openQuestions: [],
              capabilityMatch: [
                {constraint: "sell on the third day", capability: "holding_day_exit", supported: false, note: "not executable"},
              ],
              materialQuery: {
                publicTerms: ["mean reversion"],
                providerId: "crossref",
                purpose: "public_literature",
                policyRevision: "material-query-2026-11-01",
              },
            },
          }}
        />
      </I18nProvider>,
    );
    expect(screen.getByTestId("research-proposal")).toHaveAttribute("data-proposal-status", "open");
    expect(screen.getByTestId("proposal-original")).toHaveTextContent("buy cheap stocks");
    expect(screen.getByTestId("proposal-rule")).toHaveTextContent("Suggested by the system");
    expect(screen.getByTestId("proposal-meaning")).toHaveTextContent("changes the original wording");
    expect(screen.getByTestId("proposal-changes")).toHaveTextContent("You specified");
    expect(screen.getByTestId("proposal-capabilities")).toHaveTextContent("Not supported");
    expect(screen.getByTestId("proposal-material")).toHaveTextContent("mean reversion");
    await tickYahooAndRun();
    await waitFor(() => expect(payloads).toHaveLength(1));
    expect(payloads[0]).toMatchObject({
      type: "confirm_run",
      research_id: "r-spy",
      expected_revision: 4,
      reply_to: "p-card",
    });
  });

  it("keeps Run disabled when the proposal is stale", async () => {
    const confirmRun = vi.fn(async () => undefined);
    render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard
          api={shell(confirmRun)}
          view={{
            ...view,
            revision: 4,
            proposal: {
              proposalId: "p-stale",
              baseRevision: 1,
              kind: "interpret_brief",
              intent: "provide",
              status: "stale",
              nextStep: "这份提议已经过期。请再核对设定，确认后才能开跑。",
              originalThesis: "美股均值回归",
              executableRule: "",
              executableRuleSource: "",
              meaningNote: "",
              quotes: [],
              changes: [],
              openQuestions: [],
              capabilityMatch: [],
              materialQuery: null,
            },
          }}
        />
      </I18nProvider>,
    );
    expect(screen.getByTestId("proposal-next-step")).toHaveTextContent("下一步");
    expect(screen.getByTestId("proposal-next-step")).toHaveTextContent("这份提议已经过期");
    expect(screen.getByTestId("proposal-original").querySelector("[data-user-content]")).toHaveTextContent(
      "美股均值回归",
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    fireEvent.click(screen.getByTestId("unlicensed-ack"));
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    expect(confirmRun).not.toHaveBeenCalled();
  });

  it("keeps English confirm chrome free of system CJK while the user's words stay", () => {
    const executable = "日频截面均值回归（前一日信号）。未支持的限制不会悄悄删掉。";
    const meaning = "原来的说法不会照原样执行。改成均值回归后，赚的是价格偏离后的回归，不是原来的趋势或突破。";
    const momentumNote = "趋势、动量和突破不能在这里执行。原话会保留，不会改写成均值回归。";
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard
          api={shell(vi.fn())}
          view={{
            ...view,
            settings: {
              ...view.settings,
              thesis: "美股股票 AAPL 的均值回归",
            },
            proposal: {
              proposalId: "p-us",
              baseRevision: 4,
              kind: "interpret_brief",
              intent: "provide",
              status: "open",
              nextStep: "",
              originalThesis: "美股股票 AAPL 的均值回归",
              executableRule: executable,
              executableRuleSource: "system_suggested",
              meaningNote: "",
              quotes: [],
              changes: [{field: "coverage_floor", source: "user_specified", text: "1/10/5.0", quoteRef: "q0"}],
              openQuestions: [],
              capabilityMatch: [],
              materialQuery: {
                publicTerms: ["mean reversion"],
                providerId: "crossref",
                purpose: "public_literature",
                policyRevision: "material-query-2026-11-01",
              },
            },
          }}
        />
      </I18nProvider>,
    );
    const card = screen.getByTestId("confirm-run-card");
    expect(card).toHaveTextContent("AAPL");
    expect(screen.getByTestId("proposal-original").querySelector("[data-user-content]")).toHaveTextContent(
      "美股股票 AAPL 的均值回归",
    );
    expect(screen.getByTestId("proposal-rule")).toHaveTextContent("Daily cross-sectional mean reversion");
    expect(screen.getByTestId("proposal-rule")).toHaveTextContent("Suggested by the system");
    expect(screen.getByTestId("proposal-rule").textContent).not.toMatch(/[\u3400-\u9fff]/);
    expect(chromeText(card)).not.toMatch(/[\u3400-\u9fff]/);
    unmount();

    render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard
          api={shell(vi.fn())}
          view={{
            ...view,
            proposal: {
              proposalId: "p-mom",
              baseRevision: 5,
              kind: "interpret_brief",
              intent: "correct",
              status: "quotes_unavailable",
              nextStep: "报价现在不可用。等数据恢复，或改用有报价的标的后再开跑。",
              originalThesis: "美股动量策略",
              executableRule: executable,
              executableRuleSource: "system_suggested",
              meaningNote: meaning,
              quotes: [],
              changes: [{field: "thesis", source: "user_specified", text: "美股动量策略", quoteRef: "q0"}],
              openQuestions: [{
                field: "thesis",
                question: "“便宜”会改变策略含义。你指的是价格相对近期的偏离，还是估值便宜？还没说明之前，不会当成你已经同意均值回归。",
                changesMeaning: true,
              }],
              capabilityMatch: [
                {
                  constraint: "美股动量策略",
                  capability: "family.momentum",
                  supported: false,
                  note: momentumNote,
                },
                {
                  constraint: "第三天卖出",
                  capability: "holding_day_exit",
                  supported: false,
                  note: "引擎没有固定第 N 天卖出。这条限制会保留，不会悄悄删掉。",
                },
              ],
              materialQuery: null,
            },
          }}
        />
      </I18nProvider>,
    );
    const momentum = screen.getByTestId("confirm-run-card");
    expect(screen.getByTestId("proposal-meaning")).toHaveTextContent("will not run as written");
    expect(screen.getByTestId("proposal-meaning").textContent).not.toMatch(/[\u3400-\u9fff]/);
    expect(screen.getByTestId("proposal-next-step")).toHaveTextContent("Quotes are unavailable");
    expect(screen.getByTestId("proposal-questions")).toHaveTextContent("Cheap");
    expect(screen.getByTestId("proposal-capabilities")).toHaveTextContent("Sell on the third day");
    expect(screen.getByTestId("proposal-capabilities")).toHaveTextContent("not quietly dropped");
    const userBits = momentum.querySelectorAll("[data-user-content]");
    const userText = [...userBits].map((node) => node.textContent).join("\n");
    expect(userText).toContain("美股动量策略");
    expect(chromeText(momentum)).not.toMatch(/[\u3400-\u9fff]/);
  });
});

function chromeText(root: HTMLElement): string {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const parts: string[] = [];
  let node = walker.nextNode();
  while (node) {
    const parent = node.parentElement;
    if (!(parent && parent.closest("[data-user-content]"))) parts.push(node.nodeValue || "");
    node = walker.nextNode();
  }
  return parts.join("");
}
