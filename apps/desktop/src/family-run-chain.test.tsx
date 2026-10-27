/**
 * Call chain: confirm card → bindDesktopApi → engine payload.
 * The card notice and the Run button come from the same gate.
 */
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {bindDesktopApi} from "./api-bind";
import {confirmRunEnginePayload} from "./confirmRunCommand";
import {sendDialogueEnginePayload} from "./dialogueCommand";
import type {DesktopApi, DesktopView} from "./contracts";
import {enCatalog, isFinalMessageKey, zhCatalog} from "./i18n/catalog";
import {I18nProvider} from "./i18n/I18nProvider";
import {localizeKnownCopy} from "./i18n/productCopy";
import {translate} from "./i18n/translate";
import {CompletedScreen} from "./screens/CompletedScreen";
import {ConfirmRunCard, ConfirmRunScreen} from "./screens/ConfirmRunScreen";
import {GlossaryScreen} from "./screens/GlossaryScreen";
import {MethodDetail} from "./screens/MethodsScreen";

const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const CJK = /[\u3400-\u9fff]/;

afterEach(() => cleanup());

type ConfirmView = Extract<DesktopView, {kind: "confirm_run"}>;

function card(extra: Partial<ConfirmView> = {}): ConfirmView {
  return {
    kind: "confirm_run",
    researchId: "r-family",
    dialogue: [{role: "assistant", text: "原理想靠什么赚钱？例如：美股大市值股票的均值回归。"}],
    settings: {
      thesis: "美股动量策略",
      universe: "美股 · 股票",
      max_effective_hours: "12 小时",
      round1_methods: "换手成本",
      coverage_floor: "至少 1 个标的",
    },
    symbolSelection: {
      count: 1,
      listName: "用户指定标的",
      listVersion: "user",
      symbols: ["SPY"],
      source: "user_override",
      dataStart: "2014-10-27",
      dataEnd: "2026-10-24",
      dataCutoff: "2026-10-24",
      dataSource: "待选择",
      dataSourceId: null,
      dataSourcePending: true,
      priceSources: [
        {
          id: "yahoo_daily",
          label: "雅虎日线",
          unlicensed: true,
          market: "US",
          acknowledgedAt: "2026-10-24T08:25:00+00:00",
        },
      ],
    },
    market: "US",
    ...extra,
  };
}

function api(confirmRun: DesktopApi["confirmRun"]): DesktopApi {
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

function renderCard(language: typeof ZH | typeof EN, view: ConfirmView, confirmRun?: DesktopApi["confirmRun"]) {
  const payloads: unknown[] = [];
  const bound = bindDesktopApi(
    api(confirmRun ?? (async (researchId, options) => {
      payloads.push(confirmRunEnginePayload(researchId, options));
    })),
    {refresh: async () => undefined, onError: () => undefined},
  );
  const shown = render(
    <I18nProvider initial={language}>
      <ConfirmRunCard api={bound} view={view} />
    </I18nProvider>,
  );
  return {payloads, ...shown, bound};
}

const completed = (passed: boolean): Extract<DesktopView, {kind: "completed"}> => ({
  kind: "completed",
  researchId: "r-done",
  version: 1,
  status: passed ? "completed" : "ended",
  title: "均值回归",
  effective: "1 分钟",
  remaining: "11 小时",
  rounds: [],
  sources: "未找到相关资料",
  selectedRoundId: "r1",
  selectedMethodId: "cost.turnover",
  metrics: {excessAnn: 0.012, maxDrawdown: -0.2},
  eligibility: {
    allMethodsPassed: passed,
    noPendingConfirm: true,
    reverifiesPassed: true,
    pitExecutedAndPassed: true,
  },
  exportKind: passed ? "strategy_pack" : "research_record_only",
});

describe("family run gate on the confirm card", () => {
  it("disables Run and states the family reason while the card says momentum is unsupported", () => {
    const {payloads} = renderCard(ZH, card({
      meanReversionOnlyNotice: "暂不支持。不推荐最接近的族，不推荐均值回归。动量是第二批首个新增族",
      runGate: {runnable: false, code: "STRATEGY_FAMILY_NOT_RUNNABLE"},
    }));
    expect(screen.getByTestId("mean-reversion-only-notice")).toHaveTextContent("暂不支持");
    const button = screen.getByTestId("confirm-run-start");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("data-run-blocked", "family");
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent("这一族还不能开跑。");
    fireEvent.click(button);
    expect(payloads).toEqual([]);
  });

  it("disables Run with N3 when the server still says the universe is short and no source is selected", () => {
    const {payloads} = renderCard(EN, card({
      runGate: {
        runnable: false,
        code: "UNIVERSE_TOO_FEW_SYMBOLS",
        params: {count: 1, minimum: 25},
      },
    }));
    const button = screen.getByTestId("confirm-run-start");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("data-run-blocked", "source");
    expect(button).toHaveClass("is-disabled");
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(
      "No data source selected yet. Pick one on the confirmation card before running.",
    );
    expect(screen.getByTestId("confirm-run-blocked-reason")).not.toHaveTextContent("coverage minimum");
    fireEvent.click(button);
    expect(payloads).toEqual([]);
  });

  it("sends an already-acknowledged Yahoo source through api-bind without asking again", async () => {
    const {payloads} = renderCard(EN, card({
      settings: {
        thesis: "SPY mean reversion",
        universe: "US · equities",
        max_effective_hours: "12 h",
        round1_methods: "turnover",
        coverage_floor: "1 name",
      },
      meanReversionOnlyNotice: null,
      runGate: {runnable: false, code: "DATA_SOURCE_UNBOUND"},
    }));
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(
      "No data source selected yet. Pick one on the confirmation card before running.",
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    const button = screen.getByTestId("confirm-run-start");
    expect(button).toBeEnabled();
    expect(screen.queryByTestId("unlicensed-ack")).toBeNull();
    fireEvent.click(button);
    await waitFor(() => expect(payloads).toEqual([
      {
        type: "confirm_run",
        research_id: "r-family",
        data_source_id: "yahoo_daily",
      },
    ]));
  });

  it("clears a stale unlicensed error when the stored acknowledgement is what the gate sees", async () => {
    const unacked = card({
      symbolSelection: {
        ...card().symbolSelection!,
        priceSources: [
          {id: "yahoo_daily", label: "雅虎日线", unlicensed: true, market: "US", acknowledgedAt: null},
        ],
      },
      runGate: {runnable: false, code: "DATA_SOURCE_UNBOUND"},
    });
    const {rerender, bound} = renderCard(EN, unacked, async () => {
      throw new Error(JSON.stringify({
        error: "使用未经许可的数据前，请确认仅用于个人研究。",
        code: "UNLICENSED_SOURCE_UNACKNOWLEDGED",
        params: {},
      }));
    });
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    fireEvent.click(screen.getByTestId("unlicensed-ack"));
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    expect(await screen.findByTestId("confirm-run-error")).toHaveTextContent(
      "Before using an unlicensed source",
    );
    rerender(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={bound} view={card({
          runGate: {runnable: false, code: "DATA_SOURCE_UNBOUND"},
        })} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    expect(screen.queryByTestId("confirm-run-error")).toBeNull();
    expect(screen.getByTestId("confirm-run-start")).toBeEnabled();
  });
});

const QUESTION =
  "V1 only supports cross-sectional mean reversion (reversal). Your thesis will be recorded but won't change the strategy. Continue with mean reversion?";
const ACK_REASON = "Confirm whether to continue with mean reversion before running.";

describe("disclosed family stays disabled until the user answers yes", () => {
  it("keeps Run disabled before the answer and sends confirm_run after", async () => {
    const before = card({
      settings: {
        thesis: "美股低波策略",
        universe: "美股 · 股票",
        max_effective_hours: "12 小时",
        round1_methods: "换手成本",
        coverage_floor: "至少 1 个标的",
      },
      meanReversionOnlyNotice:
        "V1 只支持截面均值回归（反转）；你的论点会被记录但不会改变策略。要按均值回归继续吗？",
      runGate: {runnable: false, code: "MEAN_REVERSION_ACK_REQUIRED"},
    });
    const {payloads, rerender, bound} = renderCard(EN, before);
    const blocked = screen.getByTestId("confirm-run-start");
    expect(blocked).toBeDisabled();
    expect(blocked).toHaveAttribute("data-run-blocked", "ack");
    expect(screen.getByTestId("mean-reversion-only-notice")).toHaveTextContent(QUESTION);
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(ACK_REASON);
    fireEvent.click(blocked);
    expect(payloads).toEqual([]);

    rerender(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={bound} view={card({
          settings: before.settings,
          meanReversionOnlyNotice:
            "策略族：均值回归（V1 唯一）· 论点文字仅作记录，不改变策略",
          runGate: {runnable: false, code: "DATA_SOURCE_UNBOUND"},
        })} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    const ready = screen.getByTestId("confirm-run-start");
    expect(ready).toBeEnabled();
    expect(screen.queryByTestId("confirm-run-blocked-reason")).toBeNull();
    fireEvent.click(ready);
    await waitFor(() => expect(payloads).toEqual([
      {
        type: "confirm_run",
        research_id: "r-family",
        data_source_id: "yahoo_daily",
      },
    ]));
  });
});

describe("family re-pick names the chosen family", () => {
  it("renders the glossary name in zh and en, with no CJK in English", () => {
    const cases = [
      ["low_volatility", "低波", "low volatility"],
      ["stock_bond_rebalance", "股债再平衡", "stock-bond rebalance"],
      ["mean_reversion", "均值回归", "mean reversion"],
      ["fundamental_factor", "基本面因子", "fundamental factor"],
      ["all_weather", "全天候", "all weather"],
    ] as const;
    for (const [familyId, zhName, enName] of cases) {
      const sentence = `已改用${zhName}。你原来的论点没有采纳，这一族的方向和你的原话不同。`;
      const view = card({
        repickedFamily: familyId,
        meanReversionOnlyNotice: sentence,
        runGate: {runnable: familyId === "mean_reversion"},
      });
      const zh = renderCard(ZH, view);
      expect(screen.getByTestId("mean-reversion-only-notice")).toHaveTextContent(
        `已改用${zhName}。你原来的论点没有采纳，这一族的方向和你的原话不同。`,
      );
      expect(screen.getByTestId("mean-reversion-only-notice")).toHaveAttribute("data-repick-family", familyId);
      zh.unmount();

      const en = renderCard(EN, view);
      const notice = screen.getByTestId("mean-reversion-only-notice");
      expect(notice).toHaveTextContent(
        `Switched to ${enName}. Your original thesis was not adopted, and this family's direction differs from what you said.`,
      );
      expect(notice.textContent ?? "").not.toMatch(CJK);
      en.unmount();

      const fromSentence = localizeKnownCopy(sentence, (key, params) => translate("en", key, params));
      expect(fromSentence).toBe(
        `Switched to ${enName}. Your original thesis was not adopted, and this family's direction differs from what you said.`,
      );
      expect(fromSentence).not.toMatch(CJK);
    }
  });

  it("keeps the follow-up in glossary order and off the momentum, trend, and breakout card", () => {
    expect(zhCatalog.ui.dialogue.familyFollowUp).toBe(
      "没能对上已支持的策略族。可以说低波、股债再平衡、均值回归、基本面因子或全天候。",
    );
    expect(enCatalog.ui.dialogue.familyFollowUp).toBe(
      "That didn't match a supported strategy family. You can say low volatility, stock-bond rebalance, mean reversion, fundamental factor, or all weather.",
    );
    expect(enCatalog.ui.dialogue.familyFollowUp).not.toMatch(CJK);
    expect(enCatalog.errors.codes.MEAN_REVERSION_ACK_REQUIRED).toBe(ACK_REASON);
    expect(zhCatalog.errors.codes.MEAN_REVERSION_ACK_REQUIRED).toBe("先确认是否按均值回归继续，再开跑。");
    for (const thesis of ["美股动量策略", "美股趋势策略", "美股突破策略"]) {
      renderCard(EN, card({
        settings: {
          thesis,
          universe: "美股 · 股票",
          max_effective_hours: "12 小时",
          round1_methods: "换手成本",
          coverage_floor: "至少 1 个标的",
        },
        meanReversionOnlyNotice: "暂不支持。不推荐最接近的族，不推荐均值回归。动量是第二批首个新增族",
        runGate: {runnable: false, code: "STRATEGY_FAMILY_NOT_RUNNABLE"},
      }));
      const notice = screen.getByTestId("mean-reversion-only-notice").textContent ?? "";
      expect(notice).toContain("Not supported yet");
      expect(notice).not.toContain("didn't match a supported strategy family");
      expect(notice).not.toContain(enCatalog.ui.dialogue.familyFollowUp);
      cleanup();
    }
  });
});

describe("family answers on the confirm card", () => {
  const answered = card({
    chatEnabled: true,
    meanReversionChoice: true,
    familyChipIds: [],
    runGate: {runnable: false, code: "MEAN_REVERSION_ACK_REQUIRED"},
  });

  function renderAnswer(language: typeof ZH | typeof EN, view = answered) {
    const sent: {researchId: string; message: string}[] = [];
    const raw = api(async () => undefined);
    raw.sendDialogue = async (researchId, message) => {
      sent.push({researchId, message});
    };
    const bound = bindDesktopApi(raw, {refresh: async () => undefined, onError: () => undefined});
    const shown = render(
      <I18nProvider initial={language}>
        <ConfirmRunScreen api={bound} view={view} />
      </I18nProvider>,
    );
    return {sent, ...shown};
  }

  it("keeps the chat input enabled and sends both answers through send_dialogue", () => {
    const zh = renderAnswer(ZH);
    expect(screen.getByTestId("dialogue-input")).toBeEnabled();
    expect(screen.getByTestId("mean-reversion-continue")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("mean-reversion-decline")).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByTestId("mean-reversion-continue"));
    fireEvent.click(screen.getByTestId("mean-reversion-decline"));
    expect(zh.sent.map((item) => sendDialogueEnginePayload(item.researchId, item.message))).toEqual([
      sendDialogueEnginePayload("r-family", "按均值回归继续"),
      sendDialogueEnginePayload("r-family", "不继续"),
    ]);
    zh.unmount();

    const en = renderAnswer(EN);
    expect(screen.getByTestId("dialogue-input")).toBeEnabled();
    fireEvent.click(screen.getByTestId("mean-reversion-continue"));
    fireEvent.click(screen.getByTestId("mean-reversion-decline"));
    expect(en.sent.map((item) => item.message)).toEqual([
      "Continue with mean reversion",
      "Don't continue",
    ]);
    en.unmount();

    renderAnswer(EN, card({chatEnabled: false, runGate: {runnable: true}}));
    expect(screen.queryByTestId("dialogue-input")).toBeNull();
  });

  it("renders glossary-order chips with none preselected", () => {
    const ids = [
      "low_volatility",
      "stock_bond_rebalance",
      "mean_reversion",
      "fundamental_factor",
      "all_weather",
    ];
    const zh = renderAnswer(ZH, card({
      chatEnabled: true,
      familyChipIds: ids,
      runGate: {runnable: false, code: "STRATEGY_FAMILY_NOT_RUNNABLE"},
    }));
    expect(screen.getByTestId("family-chip-label")).toHaveTextContent("改选策略族：");
    const buttons = ids.map((id) => screen.getByTestId(`family-chip-${id}`));
    expect(buttons.map((button) => button.getAttribute("data-family-id"))).toEqual(ids);
    for (const button of buttons) {
      expect(button).toHaveAttribute("aria-pressed", "false");
    }
    fireEvent.click(screen.getByTestId("family-chip-mean_reversion"));
    expect(zh.sent[0]).toEqual({researchId: "r-family", message: "均值回归"});
    expect(sendDialogueEnginePayload(zh.sent[0].researchId, zh.sent[0].message).type).toBe("send_dialogue");
    zh.unmount();

    renderAnswer(EN, card({
      chatEnabled: true,
      familyChipIds: ["mean_reversion"],
      runGate: {runnable: false, code: "STRATEGY_FAMILY_NOT_RUNNABLE"},
    }));
    expect(screen.getByTestId("family-chip-label")).toHaveTextContent("Pick a strategy family:");
    expect(screen.getAllByTestId(/family-chip-/).filter((node) => node.getAttribute("data-family-id"))).toHaveLength(1);
    expect(screen.getByTestId("family-chip-mean_reversion")).toHaveTextContent("Mean reversion");
    expect(screen.getByTestId("family-chip-mean_reversion")).toHaveAttribute("aria-pressed", "false");
  });

  it("states that no data source is selected without changing the field value", () => {
    renderAnswer(EN, card({
      chatEnabled: false,
      runGate: {runnable: false, code: "DATA_SOURCE_UNBOUND"},
    }));
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(
      "No data source selected yet. Pick one on the confirmation card before running.",
    );
    expect(screen.getByTestId("confirm-run-blocked-reason")).not.toHaveTextContent("Not selected");
  });
});

describe("completed result chip and metrics", () => {
  it("shows the result, not the check name, and the two metrics in both languages", () => {
    render(
      <I18nProvider initial={ZH}>
        <CompletedScreen api={api(vi.fn())} view={completed(false)} />
      </I18nProvider>,
    );
    const pills = screen.getByTestId("completed-gate-pills").textContent ?? "";
    expect(pills).toContain("验证未全部通过");
    expect(pills).not.toContain("验证方法全部通过");
    expect(pills).not.toContain("当前验证方法全部通过");
    expect(screen.getByTestId("completed-excess-ann")).toHaveTextContent("1.2%");
    expect(screen.getByTestId("completed-max-dd")).toHaveTextContent("-20.0%");
    expect(screen.getByTestId("completed-sources")).toHaveTextContent("未找到相关资料");
    cleanup();
    render(
      <I18nProvider initial={EN}>
        <CompletedScreen api={api(vi.fn())} view={completed(false)} />
      </I18nProvider>,
    );
    const enPills = screen.getByTestId("completed-gate-pills").textContent ?? "";
    expect(enPills).toContain("Not all validation methods passed");
    expect(enPills).not.toContain("All validation methods passed");
    expect(screen.getByTestId("completed-metrics").textContent).toContain("Annualized excess return");
    expect(screen.getByTestId("completed-metrics").textContent).toContain("Maximum drawdown");
    cleanup();
    render(
      <I18nProvider initial={EN}>
        <CompletedScreen api={api(vi.fn())} view={completed(true)} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("completed-gate-pills").textContent).toContain("All validation methods passed");
  });
});

describe("English surfaces that used to render engine Chinese", () => {
  it("renders glossary, methods, dialogue, and the round change with no CJK", () => {
    const en = (text: string) => localizeKnownCopy(text, (key, params) => translate("en", key, params));
    expect(en("原理想靠什么赚钱？例如：美股大市值股票的均值回归。")).not.toMatch(CJK);
    expect(en("没能理解你的意思。原理想靠什么赚钱？例如：美股大市值股票的均值回归。")).not.toMatch(CJK);
    expect(en("变更：延续锁定论点下的参数/模型迭代")).toBe(
      "Change: Continue parameter and model iteration under the locked thesis",
    );
    expect(en("未命名研究")).toBe("Untitled study");
    expect(enCatalog.ui.completed.maxDrawdown).toBe(enCatalog.ui.surface.drawdownName);
    expect(zhCatalog.ui.completed.maxDrawdown).toBe(zhCatalog.ui.surface.drawdownName);
    expect(enCatalog.ui.completed.excessAnn).toBe("Annualized excess return");
    expect(enCatalog.errors.codes.STRATEGY_FAMILY_NOT_RUNNABLE).toBe(
      "This strategy family can't run yet.",
    );
    for (const key of [
      "ui.completed.excessAnn",
      "ui.completed.maxDrawdown",
      "errors.codes.STRATEGY_FAMILY_NOT_RUNNABLE",
      "ui.copy.meanReversionQuestion",
      "ui.copy.familyRepick",
      "ui.dialogue.familyFollowUp",
      "errors.codes.MEAN_REVERSION_ACK_REQUIRED",
      "ui.surface.pitPurpose",
      "ui.glossaryBody.pit",
    ] as const) {
      expect(isFinalMessageKey(key), key).toBe(true);
    }
    expect(en("试验次数（X/N）与累计 M")).not.toMatch(CJK);

    render(
      <I18nProvider initial={EN}>
        <GlossaryScreen view={{
          kind: "glossary",
          intro: "这些是界面和导出包里使用的展示名。方法的 id 与修订号没有改，计算也没有改。对话里仍可输入旧称，会解析成同一个方法。",
          entries: [
            {id: "trial_counts", term: "试验次数（X/N）与累计 M", body: "中文正文"},
            {id: "cost_bp", term: "成本（bp）", body: "中文成本"},
            {id: "pit.consistency", term: "时点一致性", body: "中文时点"},
          ],
        }} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("glossary-page").textContent).not.toMatch(CJK);
    cleanup();

    render(
      <I18nProvider initial={EN}>
        <MethodDetail api={api(vi.fn())} method={{
          id: "cost.turnover",
          name: "换手成本",
          revision: "cost-v1",
          revisionLabel: "换手成本 · 内置第 1 版",
          description: "在换手成本下检验净超额是否仍为正。",
          definitionDisplay: "用途：在换手成本下检验净超额是否仍为正。\n美股成本（bp）：10\nA 股成本（bp）：20",
          source: "preset",
          category: "成本",
          dimensions: [{
            kind: "cost_sensitivity",
            kindLabel: "成本敏感度",
            name: "净超额",
            description: "净超额",
            passThreshold: 0,
            comparison: "gt",
            comparisonLabel: "大于",
            failureDisplay: "净超额不为正",
          }],
        }} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("method-definition-display").textContent).not.toMatch(CJK);
    expect(document.body.textContent).not.toMatch(CJK);
  });
});
