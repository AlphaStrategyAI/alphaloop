/**
 * Call chain: confirm card → bindDesktopApi → Tauri invoke payload.
 * A dropped argument here is how a green unit test still shipped a dead button.
 */
import "@testing-library/jest-dom/vitest";
import {act, cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {bindDesktopApi} from "./api-bind";
import {ConfirmRunCard} from "./screens/ConfirmRunScreen";
import type {DesktopView} from "./contracts";
import {createTauriDesktopApi, type DesktopInvoke} from "./desktopApi";
import {I18nProvider} from "./i18n/I18nProvider";

const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

afterEach(() => cleanup());

function viewWith(resolution: NonNullable<Extract<DesktopView, {kind: "confirm_run"}>["symbolResolution"]>): Extract<DesktopView, {kind: "confirm_run"}> {
  return {
    kind: "confirm_run",
    researchId: "r-symbol",
    dialogue: [],
    chatEnabled: false,
    settings: {
      thesis: "A股股票 600519 均值回归",
      universe: "A股 · 股票",
      max_effective_hours: "12 小时",
      round1_methods: "走样检验",
      coverage_floor: "至少 1 个标的",
    },
    symbolSelection: resolution.symbols.length
      ? {
          count: resolution.symbols.length,
          listName: "用户指定标的",
          listVersion: "用户",
          symbols: resolution.symbols,
          source: "user_override",
          dataStart: "2014-10-19",
          dataEnd: "2026-10-19",
          dataCutoff: "2026-10-19",
          dataSource: "AkShare 日线（新浪优先）",
        }
      : undefined,
    symbolResolution: resolution,
  };
}

function renderCard(
  language: typeof ZH | typeof EN,
  resolution: NonNullable<Extract<DesktopView, {kind: "confirm_run"}>["symbolResolution"]>,
  extra: Partial<Extract<DesktopView, {kind: "confirm_run"}>> = {},
) {
  const invoke = vi.fn(async () => undefined);
  const raw = createTauriDesktopApi(invoke as unknown as DesktopInvoke);
  const bound = bindDesktopApi(raw, {
    onError: vi.fn(),
    refresh: vi.fn(async () => undefined),
  });
  const base = viewWith(resolution);
  const view = {
    ...base,
    ...extra,
    symbolSelection: extra.symbolSelection ?? base.symbolSelection,
  };
  render(
    <I18nProvider initial={language}>
      <ConfirmRunCard api={bound} view={view} />
    </I18nProvider>,
  );
  return {invoke};
}

describe("symbol resolution call chain", () => {
  it("shows the inferred symbol and sends the edited symbol through to the engine", async () => {
    const recognized = {
      blocked: false,
      code: null,
      token: "600519",
      symbol: "600519.SH",
      symbols: ["600519.SH"],
      inferred: [{raw: "600519", symbol: "600519.SH"}],
      editable: true,
    };
    const zh = renderCard(ZH, recognized);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 600519.SH");
    const input = screen.getByTestId("symbol-edit") as HTMLInputElement;
    expect(input.value).toBe("600519.SH");
    expect(input).toBeEnabled();
    expect(screen.getByTestId("confirm-run-start")).toBeEnabled();
    fireEvent.change(input, {target: {value: "000001.SZ"}});
    fireEvent.blur(input);
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("set_research_symbol", {
        researchId: "r-symbol",
        symbol: "000001.SZ",
      }),
    );
    cleanup();

    const en = renderCard(EN, recognized);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("Recognized as 600519.SH");
    fireEvent.change(screen.getByTestId("symbol-edit"), {target: {value: "510300.SH"}});
    fireEvent.blur(screen.getByTestId("symbol-edit"));
    await waitFor(() =>
      expect(en.invoke).toHaveBeenCalledWith("set_research_symbol", {
        researchId: "r-symbol",
        symbol: "510300.SH",
      }),
    );
  });

  it("blocks Run and names the unresolved token in zh and en", async () => {
    const blocked = {
      blocked: true,
      code: "SYMBOL_UNRESOLVED" as const,
      token: "900901",
      symbol: null,
      symbols: [] as string[],
      inferred: [],
      editable: true,
    };
    const zh = renderCard(ZH, blocked);
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "无法确认「900901」属于哪个交易所。请选择交易所，或输入带后缀的完整代码。",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    expect(zh.invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
    fireEvent.click(screen.getByTestId("symbol-pick-SH"));
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("set_research_symbol", {
        researchId: "r-symbol",
        symbol: "900901.SH",
      }),
    );
    cleanup();

    renderCard(EN, blocked);
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "Can't tell which exchange “900901” trades on. Pick an exchange or enter the full code with its suffix.",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
  });

  it("blocks Run when the source has no data for the resolved symbol", () => {
    const missing = {
      blocked: true,
      code: "SYMBOL_NO_DATA" as const,
      token: "609999",
      symbol: "609999.SH",
      symbols: ["609999.SH"],
      inferred: [{raw: "609999", symbol: "609999.SH"}],
      editable: true,
    };
    const zh = renderCard(ZH, missing);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 609999.SH");
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "所选数据源没有 609999.SH 的行情，无法开跑。请改代码或换数据源。",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    expect(zh.invoke).not.toHaveBeenCalled();
    cleanup();

    renderCard(EN, missing);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("Recognized as 609999.SH");
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "The selected data source has no data for 609999.SH, so the run can't start. Change the symbol or the data source.",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
  });

  it("does not block Run for an amount or for indicator and prose words", async () => {
    const open: Extract<DesktopView, {kind: "confirm_run"}> = {
      kind: "confirm_run",
      researchId: "r-prose",
      dialogue: [],
      chatEnabled: false,
      settings: {
        thesis: "用 100000 元本金做A股股票 RSI MACD FIND CAPS TECH 均值回归",
        universe: "A股 · 股票",
        max_effective_hours: "12 小时",
        round1_methods: "走样检验",
        coverage_floor: "至少 25 个标的",
      },
      symbolSelection: {
        count: 300,
        listName: "A股大市值",
        listVersion: "2",
        symbols: ["600519.SH"],
        source: "default_pool",
        dataStart: "2014-10-19",
        dataEnd: "2026-10-19",
        dataCutoff: "2026-10-19",
        dataSource: "AkShare 日线（新浪优先）",
        isDefaultPool: true,
      },
    };
    for (const language of [ZH, EN]) {
      const invoke = vi.fn(async () => undefined);
      const bound = bindDesktopApi(createTauriDesktopApi(invoke as unknown as DesktopInvoke), {
        onError: vi.fn(),
        refresh: vi.fn(async () => undefined),
      });
      render(
        <I18nProvider initial={language}>
          <ConfirmRunCard api={bound} view={open} />
        </I18nProvider>,
      );
      expect(screen.queryByTestId("symbol-block-error")).not.toBeInTheDocument();
      expect(screen.queryByTestId("symbol-recognition")).not.toBeInTheDocument();
      fireEvent.click(screen.getByTestId("confirm-run-start"));
      await waitFor(() =>
        expect(invoke).toHaveBeenCalledWith("confirm_run", {researchId: "r-prose"}),
      );
      cleanup();
    }
  });

  it("blocks a fake US ticker with no data, in zh and en", () => {
    const fake = {
      blocked: true,
      code: "SYMBOL_NO_DATA" as const,
      token: "ZZZZQ",
      symbol: "ZZZZQ",
      symbols: ["ZZZZQ"],
      inferred: [{raw: "ZZZZQ", symbol: "ZZZZQ"}],
      editable: true,
    };
    renderCard(ZH, fake);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 ZZZZQ");
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "所选数据源没有 ZZZZQ 的行情，无法开跑。请改代码或换数据源。",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    cleanup();
    renderCard(EN, fake);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("Recognized as ZZZZQ");
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "The selected data source has no data for ZZZZQ, so the run can't start. Change the symbol or the data source.",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
  });

  it("blocks 510300 on AkShare as an unsupported ETF, in zh and en", () => {
    const etf = {
      blocked: true,
      code: "SYMBOL_ETF_UNSUPPORTED" as const,
      token: "510300",
      symbol: "510300.SH",
      symbols: ["510300.SH"],
      inferred: [{raw: "510300", symbol: "510300.SH"}],
      editable: true,
    };
    renderCard(ZH, etf);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 510300.SH");
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "所选数据源暂不支持 A 股 ETF 行情（510300.SH），无法开跑。",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    cleanup();
    renderCard(EN, etf);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("Recognized as 510300.SH");
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "The selected data source doesn't support China A-share ETF prices yet (510300.SH), so the run can't start.",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
  });

  it("joins several recognized symbols with a comma in English and keeps the label off the input", () => {
    const pair = {
      blocked: false,
      code: null,
      token: null,
      symbol: "SPY",
      symbols: ["SPY", "QQQ"],
      inferred: [
        {raw: "SPY", symbol: "SPY"},
        {raw: "QQQ", symbol: "QQQ"},
      ],
      editable: true,
    };
    renderCard(EN, pair);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("Recognized as SPY, QQQ");
    expect(screen.getByTestId("symbol-recognition").textContent).not.toContain("、");
    expect((screen.getByTestId("symbol-edit") as HTMLInputElement).value).toBe("SPY, QQQ");
    const label = screen.getByTestId("symbol-edit").closest(".symbol-edit-label");
    expect(label).not.toBeNull();
    expect(screen.getByTestId("symbol-resolution")).toHaveClass("symbol-resolution");
    cleanup();
    renderCard(ZH, pair);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 SPY、QQQ");
  });

  it("asks about COST both ways through the same invoke chain", async () => {
    const asked = {
      blocked: true,
      code: "SYMBOL_ASK_PENDING" as const,
      token: null,
      symbol: null,
      symbols: [] as string[],
      inferred: [],
      editable: true,
      asks: [{token: "COST", symbol: "COST"}],
    };
    const zh = renderCard(ZH, asked);
    expect(screen.getByTestId("symbol-ask")).toHaveTextContent(
      "COST 是美股代码，也是常见英文单词。要把它当作标的吗？",
    );
    expect(screen.getByTestId("symbol-ask-yes-COST")).toHaveTextContent("当作标的");
    expect(screen.getByTestId("symbol-ask-no-COST")).toHaveTextContent("只是文字");
    expect(screen.getByTestId("symbol-ask-block-hint")).toHaveTextContent("先确认上面的代码再开跑。");
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    expect(zh.invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
    fireEvent.click(screen.getByTestId("symbol-ask-yes-COST"));
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("answer_symbol_ask", {
        researchId: "r-symbol",
        token: "COST",
        accept: true,
      }),
    );
    cleanup();

    const en = renderCard(EN, asked);
    expect(screen.getByTestId("symbol-ask")).toHaveTextContent(
      "COST is a US ticker and also a common English word. Use it as a symbol?",
    );
    expect(screen.getByTestId("symbol-ask-yes-COST")).toHaveTextContent("Use as symbol");
    expect(screen.getByTestId("symbol-ask-no-COST")).toHaveTextContent("Just text");
    expect(screen.getByTestId("symbol-ask-block-hint")).toHaveTextContent(
      "Confirm the symbols above before running.",
    );
    fireEvent.click(screen.getByTestId("symbol-ask-no-COST"));
    await waitFor(() =>
      expect(en.invoke).toHaveBeenCalledWith("answer_symbol_ask", {
        researchId: "r-symbol",
        token: "COST",
        accept: false,
      }),
    );
  });

  it("shows $spy as a recognized symbol", () => {
    const marked = {
      blocked: false,
      code: null,
      token: "$spy",
      symbol: "SPY",
      symbols: ["SPY"],
      inferred: [{raw: "$spy", symbol: "SPY"}],
      editable: true,
    };
    renderCard(ZH, marked);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 SPY");
    expect((screen.getByTestId("symbol-edit") as HTMLInputElement).value).toBe("SPY");
    expect(screen.getByTestId("confirm-run-start")).toBeEnabled();
    cleanup();
    renderCard(EN, marked);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("Recognized as SPY");
  });

  it("offers the lowercase spy hint and sends the one-click symbol", async () => {
    const hint = {
      blocked: false,
      code: null,
      token: null,
      symbol: null,
      symbols: [] as string[],
      inferred: [],
      editable: true,
      hints: [{token: "spy", symbol: "SPY"}],
      poolCount: 503,
    };
    const zh = renderCard(ZH, hint);
    expect(screen.getByTestId("symbol-pool-hint")).toHaveTextContent(
      "没有识别到标的，将使用默认池（503 只）。你是指 SPY 吗？",
    );
    expect(screen.getByTestId("symbol-hint-use")).toHaveTextContent("设为标的");
    expect(screen.getByTestId("confirm-run-start")).toBeEnabled();
    fireEvent.click(screen.getByTestId("symbol-hint-use"));
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("use_hinted_symbol", {
        researchId: "r-symbol",
        symbol: "SPY",
      }),
    );
    cleanup();

    const one = renderCard(EN, {...hint, poolCount: 1});
    expect(screen.getByTestId("symbol-pool-hint")).toHaveTextContent(
      "No symbol recognized, so the run will use the default pool (1 name). Did you mean SPY?",
    );
    expect(screen.getByTestId("symbol-pool-hint").textContent).not.toContain("1 names");
    cleanup();
    renderCard(EN, hint);
    expect(screen.getByTestId("symbol-pool-hint")).toHaveTextContent(
      "No symbol recognized, so the run will use the default pool (503 names). Did you mean SPY?",
    );
    expect(screen.getByTestId("symbol-hint-use")).toHaveTextContent("Use as symbol");
  });

  it("blocks a mix of China A-shares and US stocks in zh and en", () => {
    const mixed = {
      blocked: true,
      code: "SYMBOL_MIXED_MARKETS" as const,
      token: null,
      symbol: null,
      symbols: ["600519.SH", "SPY"],
      inferred: [
        {raw: "600519", symbol: "600519.SH"},
        {raw: "SPY", symbol: "SPY"},
      ],
      editable: true,
      cnSymbols: "600519.SH",
      usSymbols: "SPY",
    };
    const zh = renderCard(ZH, mixed);
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "一次研究只能用同一个市场的标的，这里既有 A 股（600519.SH），也有美股（SPY）。请删掉其中一边。",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("confirm-run-start"));
    expect(zh.invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
    cleanup();
    renderCard(EN, mixed);
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "A study can only use symbols from one market, but this has both China A-shares (600519.SH) and US stocks (SPY). Remove one side.",
    );
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
  });

  it("saves a dirty symbol before confirm_run, and waits for that save", async () => {
    let releaseSave: () => void = () => undefined;
    const invoke = vi.fn((command: string) => {
      if (command === "set_research_symbol") {
        return new Promise<void>((resolve) => {
          releaseSave = resolve;
        });
      }
      return Promise.resolve();
    });
    const bound = bindDesktopApi(createTauriDesktopApi(invoke as unknown as DesktopInvoke), {
      onError: vi.fn(),
      refresh: vi.fn(async () => undefined),
    });
    const blocked = {
      blocked: true,
      code: "SYMBOL_UNRESOLVED" as const,
      token: "900901",
      symbol: null,
      symbols: [] as string[],
      inferred: [],
      editable: true,
    };
    render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={bound} view={viewWith(blocked)} />
      </I18nProvider>,
    );
    fireEvent.change(screen.getByTestId("symbol-edit"), {target: {value: "600519.SH"}});
    const button = screen.getByTestId("confirm-run-start");
    expect(button).toBeEnabled();
    fireEvent.mouseDown(button);
    fireEvent.click(button);
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("set_research_symbol", {
        researchId: "r-symbol",
        symbol: "600519.SH",
      }),
    );
    expect(invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
    await act(async () => {
      releaseSave();
    });
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("confirm_run", {researchId: "r-symbol"}),
    );
    const names = invoke.mock.calls.map((call) => call[0]);
    expect(names.indexOf("set_research_symbol")).toBeLessThan(names.indexOf("confirm_run"));
  });

  it("submits the symbol field on Enter and does not start the run", async () => {
    const {invoke} = renderCard(ZH, {
      blocked: false,
      code: null,
      token: "600519",
      symbol: "600519.SH",
      symbols: ["600519.SH"],
      inferred: [{raw: "600519", symbol: "600519.SH"}],
      editable: true,
    });
    const input = screen.getByTestId("symbol-edit");
    fireEvent.change(input, {target: {value: "000001.SZ"}});
    fireEvent.keyDown(input, {key: "Enter"});
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("set_research_symbol", {
        researchId: "r-symbol",
        symbol: "000001.SZ",
      }),
    );
    expect(invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
  });

  it("removes a recognized symbol from the card", async () => {
    const {invoke} = renderCard(ZH, {
      blocked: false,
      code: null,
      token: "SPY",
      symbol: "SPY",
      symbols: ["SPY"],
      inferred: [{raw: "SPY", symbol: "SPY"}],
      editable: true,
    });
    fireEvent.click(screen.getByTestId("symbol-remove-SPY"));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("set_research_symbol", {
        researchId: "r-symbol",
        symbol: "",
      }),
    );
  });

  it("asks about an amount-like code both ways, then change puts the ask back", async () => {
    const amount = {
      blocked: true,
      code: "SYMBOL_AMOUNT_LIKE" as const,
      token: "600519",
      symbol: "600519.SH",
      symbols: [] as string[],
      inferred: [],
      editable: true,
      asks: [{token: "600519", symbol: "600519.SH", kind: "amount" as const}],
    };
    const zh = renderCard(ZH, amount);
    expect(screen.getByTestId("symbol-ask")).toHaveTextContent(
      "「600519」看起来像金额，也可能是代码 600519.SH。要把它当作标的吗？",
    );
    expect(screen.queryByText(/交易所/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("symbol-ask-yes-600519"));
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("answer_symbol_ask", {
        researchId: "r-symbol",
        token: "600519",
        accept: true,
      }),
    );
    cleanup();
    const answered = renderCard(ZH, {
      ...amount,
      blocked: false,
      asks: [],
      symbols: ["600519.SH"],
      answers: [{token: "600519", symbol: "600519.SH", kind: "amount", accept: true}],
    });
    expect(screen.getByTestId("symbol-ask-answered")).toHaveTextContent("已当作标的：600519.SH · 更改");
    fireEvent.click(screen.getByTestId("symbol-ask-change-600519"));
    await waitFor(() =>
      expect(answered.invoke).toHaveBeenCalledWith("revert_symbol_ask", {
        researchId: "r-symbol",
        token: "600519",
      }),
    );
    cleanup();
    const en = renderCard(EN, amount);
    expect(screen.getByTestId("symbol-ask")).toHaveTextContent(
      '"600519" looks like an amount, but it could also be the symbol 600519.SH. Use it as a symbol?',
    );
    fireEvent.click(screen.getByTestId("symbol-ask-no-600519"));
    await waitFor(() =>
      expect(en.invoke).toHaveBeenCalledWith("answer_symbol_ask", {
        researchId: "r-symbol",
        token: "600519",
        accept: false,
      }),
    );
  });

  it("lists at most three hint candidates and the second button sets that symbol", async () => {
    const {invoke} = renderCard(EN, {
      blocked: false,
      code: null,
      token: null,
      symbol: null,
      symbols: [],
      inferred: [],
      editable: true,
      hints: [
        {token: "on", symbol: "ON"},
        {token: "an", symbol: "AN"},
        {token: "it", symbol: "IT"},
        {token: "low", symbol: "LOW"},
      ],
      poolCount: 503,
    });
    expect(screen.getByTestId("symbol-pool-hint")).toHaveTextContent(
      "No symbol recognized, so the run will use the default pool (503 names). Did you mean one of these?",
    );
    expect(screen.queryByTestId("symbol-hint-use-4")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("symbol-hint-use-2"));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("use_hinted_symbol", {
        researchId: "r-symbol",
        symbol: "AN",
      }),
    );
  });

  it("removes one mixed-market side without clearing the other recognition line", async () => {
    const mixed = {
      blocked: true,
      code: "SYMBOL_MIXED_MARKETS" as const,
      token: null,
      symbol: null,
      symbols: ["600519.SH", "SPY"],
      inferred: [
        {raw: "600519", symbol: "600519.SH"},
        {raw: "SPY", symbol: "SPY"},
      ],
      editable: true,
      cnSymbols: "600519.SH",
      usSymbols: "SPY",
    };
    const zh = renderCard(ZH, mixed);
    expect(screen.getByTestId("symbol-recognition")).toHaveTextContent("已识别为 600519.SH、SPY");
    expect(screen.getByTestId("symbol-remove-cn")).toHaveTextContent("移除 A 股标的");
    expect(screen.getByTestId("symbol-remove-us")).toHaveTextContent("移除美股标的");
    fireEvent.click(screen.getByTestId("symbol-remove-us"));
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("remove_market_side", {
        researchId: "r-symbol",
        side: "us",
      }),
    );
    cleanup();
    const en = renderCard(EN, mixed);
    expect(screen.getByTestId("symbol-remove-cn")).toHaveTextContent("Remove A-share symbols");
    expect(screen.getByTestId("symbol-remove-us")).toHaveTextContent("Remove US symbols");
    fireEvent.click(screen.getByTestId("symbol-remove-cn"));
    await waitFor(() =>
      expect(en.invoke).toHaveBeenCalledWith("remove_market_side", {
        researchId: "r-symbol",
        side: "cn",
      }),
    );
  });

  it("names the symbol on a recognition remove button", () => {
    renderCard(ZH, {
      blocked: false,
      code: null,
      token: "SPY",
      symbol: "SPY",
      symbols: ["SPY"],
      inferred: [{raw: "SPY", symbol: "SPY"}],
      editable: true,
    });
    expect(screen.getByTestId("symbol-remove-SPY")).toHaveTextContent("移除 SPY");
    cleanup();
    renderCard(EN, {
      blocked: false,
      code: null,
      token: "SPY",
      symbol: "SPY",
      symbols: ["SPY"],
      inferred: [{raw: "SPY", symbol: "SPY"}],
      editable: true,
    });
    expect(screen.getByTestId("symbol-remove-SPY")).toHaveTextContent("Remove SPY");
  });

  it("keeps the older ask sentence when the token is not the symbol", () => {
    renderCard(EN, {
      blocked: true,
      code: "SYMBOL_ASK_PENDING",
      token: null,
      symbol: null,
      symbols: [],
      inferred: [],
      editable: true,
      asks: [{token: "low price", symbol: "LOW", kind: "ask"}],
    });
    expect(screen.getByTestId("symbol-ask")).toHaveTextContent(
      '"low price" is the US ticker LOW and also a common English word. Use it as a symbol?',
    );
  });

  it("blocks a stated-market mismatch and removes that symbol through the invoke chain", async () => {
    const mismatch = {
      blocked: true,
      code: "SYMBOL_MARKET_MISMATCH" as const,
      token: null,
      symbol: null,
      symbols: [] as string[],
      inferred: [],
      editable: true,
      mismatches: ["CAPS", "TECH"],
      mismatchMarket: "CN" as const,
    };
    const zh = renderCard(ZH, mismatch);
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "描述里的市场是 A 股，但 CAPS、TECH 不属于这个市场。请删掉这些代码，或改成对应的市场。",
    );
    expect(screen.getByTestId("symbol-remove-mismatch-CAPS")).toHaveTextContent("移除 CAPS");
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(
      "描述里的市场是 A 股，但 CAPS、TECH 不属于这个市场。请删掉这些代码，或改成对应的市场。",
    );
    expect(screen.getByTestId("confirm-run-start")).toHaveAttribute("data-run-blocked", "resolution");
    fireEvent.click(screen.getByTestId("symbol-remove-mismatch-CAPS"));
    await waitFor(() =>
      expect(zh.invoke).toHaveBeenCalledWith("dismiss_mismatched_symbol", {
        researchId: "r-symbol",
        symbol: "CAPS",
      }),
    );
    cleanup();
    const en = renderCard(EN, {
      ...mismatch,
      mismatches: ["CAPS"],
    });
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "The description says China A-shares, but CAPS isn't in that market. Remove it or change the market.",
    );
    expect(screen.getByTestId("symbol-remove-mismatch-CAPS")).toHaveTextContent("Remove CAPS");
    cleanup();
    renderCard(EN, mismatch);
    expect(screen.getByTestId("symbol-block-error")).toHaveTextContent(
      "The description says China A-shares, but CAPS, TECH aren't in that market. Remove them or change the market.",
    );
  });

  it("shows an unrecognized token with the default pool and does not block Run for the token", () => {
    renderCard(
      EN,
      {
        blocked: false,
        code: null,
        token: null,
        symbol: null,
        symbols: [],
        inferred: [],
        editable: true,
        unrecognized: [{token: "TCEHY"}],
        hints: [{token: "spy", symbol: "SPY"}],
        poolCount: 503,
      },
      {
        symbolSelection: {
          count: 503,
          listName: "US large-cap universe",
          listVersion: "us_equity_large_cap_v2",
          symbols: ["SPY"],
          source: "default_pool",
          dataStart: "2014-10-19",
          dataEnd: "2026-10-19",
          dataCutoff: "2026-10-19",
          dataSource: "待选择",
          dataSourcePending: true,
          offeredDataSourceId: "yahoo_daily",
          offeredDataSource: "雅虎日线",
          priceSources: [{id: "yahoo_daily", label: "雅虎日线", unlicensed: true}],
        },
      },
    );
    expect(screen.getByTestId("symbol-unrecognized-TCEHY")).toHaveTextContent(
      '"TCEHY" wasn\'t recognized. It isn\'t on the US listings (it may be OTC or delisted), so it won\'t be used as a symbol.',
    );
    expect(screen.getByTestId("symbol-pool-hint")).toHaveTextContent("default pool");
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
  });

  it("after a market switch, Run stays blocked until an unlicensed source is chosen and acknowledged", () => {
    renderCard(
      ZH,
      {
        blocked: false,
        code: null,
        token: "SPY",
        symbol: "SPY",
        symbols: ["SPY"],
        inferred: [{raw: "SPY", symbol: "SPY"}],
        editable: true,
      },
      {
        marketSwitch: {market: "US", benchmark: "S&P 500"},
        settings: {
          thesis: "600519 和 SPY",
          universe: "美股 · 股票",
          max_effective_hours: "12 小时",
          round1_methods: "走样检验",
          coverage_floor: "至少 1 个标的",
        },
        symbolSelection: {
          count: 1,
          listName: "用户指定标的",
          listVersion: "用户",
          symbols: ["SPY"],
          source: "user_override",
          dataStart: "2014-10-19",
          dataEnd: "2026-10-19",
          dataCutoff: "2026-10-19",
          dataSource: "待选择",
          dataSourcePending: true,
          offeredDataSourceId: "yahoo_daily",
          offeredDataSource: "雅虎日线",
          priceSources: [{id: "yahoo_daily", label: "雅虎日线", unlicensed: true}],
        },
      },
    );
    expect(screen.getByTestId("market-switch-notice")).toHaveTextContent(
      "已按剩下的标的切换到美股，基准改为 S&P 500。",
    );
    const run = screen.getByTestId("confirm-run-start") as HTMLButtonElement;
    expect(run).toBeDisabled();
    fireEvent.click(screen.getByTestId("price-source-yahoo_daily"));
    expect(run).toBeDisabled();
    fireEvent.click(screen.getByTestId("unlicensed-ack"));
    expect(run).toBeEnabled();
  });

  it("asks which market when the description named none, then sends the US choice", async () => {
    const {invoke} = renderCard(
      ZH,
      {
        blocked: true,
        code: "MARKET_CHOICE_PENDING",
        token: null,
        symbol: null,
        symbols: [],
        inferred: [],
        editable: true,
      },
      {
        marketChoice: {pending: true, cnCount: 300, usCount: 503},
        settings: {
          thesis: "MACD 金叉 均值回归",
          universe: "",
          max_effective_hours: "12 小时",
          round1_methods: "走样检验",
          coverage_floor: "至少 25 个标的",
        },
      },
    );
    expect(screen.getByTestId("market-choice")).toHaveTextContent(
      "描述里没有写市场。这次研究用哪个市场的默认池？",
    );
    expect(screen.getByTestId("market-choice-cn")).toHaveTextContent("A 股大市值池（300 只）");
    expect(screen.getByTestId("market-choice-us")).toHaveTextContent("美股大市值池（503 只）");
    expect(screen.getByTestId("market-choice-cn")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("market-choice-us")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("market-choice-us"));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("choose_default_market", {
        researchId: "r-symbol",
        market: "US",
      }),
    );
    cleanup();
    const en = renderCard(
      EN,
      {
        blocked: true,
        code: "MARKET_CHOICE_PENDING",
        token: null,
        symbol: null,
        symbols: [],
        inferred: [],
        editable: true,
      },
      {marketChoice: {pending: true, cnCount: 300, usCount: 503}},
    );
    expect(screen.getByTestId("market-choice")).toHaveTextContent(
      "The description doesn't name a market. Which market's default pool should this study use?",
    );
    expect(screen.getByTestId("market-choice-cn")).toHaveTextContent("China A-share large-cap (300 names)");
    expect(screen.getByTestId("market-choice-us")).toHaveTextContent("US large-cap (503 names)");
    const run = screen.getByTestId("confirm-run-start");
    expect(run).toBeDisabled();
    expect(run).toHaveAttribute("data-run-blocked", "market");
    expect(run.className).toContain("is-disabled");
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(
      "The description doesn't name a market.",
    );
    fireEvent.click(run);
    expect(en.invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
  });

  it("ignores a picked source that belongs to the other market and keeps Run disabled", async () => {
    const invoke = vi.fn(async () => undefined);
    const raw = createTauriDesktopApi(invoke as unknown as DesktopInvoke);
    const bound = bindDesktopApi(raw, {
      onError: vi.fn(),
      refresh: vi.fn(async () => undefined),
    });
    const acknowledged = "2026-10-24T00:00:00+00:00";
    const cnSelection = {
      count: 1,
      listName: "用户指定标的",
      listVersion: "用户",
      symbols: ["600519.SH", "SPY"],
      source: "user_override" as const,
      dataStart: "2014-10-19",
      dataEnd: "2026-10-19",
      dataCutoff: "2026-10-19",
      dataSource: "待选择",
      dataSourceId: null,
      dataSourcePending: true,
      priceSources: [
        {
          id: "akshare_sina_daily",
          label: "AkShare 日线（新浪优先）",
          unlicensed: true,
          acknowledgedAt: acknowledged,
          market: "CN" as const,
        },
      ],
    };
    const base = viewWith({
      blocked: true,
      code: "SYMBOL_MIXED_MARKETS",
      token: null,
      symbol: null,
      symbols: ["600519.SH", "SPY"],
      inferred: [
        {raw: "600519", symbol: "600519.SH"},
        {raw: "SPY", symbol: "SPY"},
      ],
      editable: true,
      cnSymbols: "600519.SH",
      usSymbols: "SPY",
    });
    const {rerender} = render(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard api={bound} view={{...base, market: "CN", symbolSelection: cnSelection}} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByTestId("price-source-akshare_sina_daily"));
    expect(screen.getByTestId("confirm-run-start")).toBeDisabled();
    fireEvent.click(screen.getByTestId("symbol-remove-cn"));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("remove_market_side", {
        researchId: "r-symbol",
        side: "cn",
      }),
    );
    rerender(
      <I18nProvider initial={ZH}>
        <ConfirmRunCard
          api={bound}
          view={{
            ...base,
            market: "US",
            marketSwitch: {market: "US", benchmark: "S&P 500"},
            settings: {...base.settings, universe: "美股 · 股票"},
            symbolResolution: {
              blocked: false,
              code: null,
              token: "SPY",
              symbol: "SPY",
              symbols: ["SPY"],
              inferred: [{raw: "SPY", symbol: "SPY"}],
              editable: true,
            },
            symbolSelection: {
              ...cnSelection,
              symbols: ["SPY"],
              dataSource: "待选择",
              dataSourceId: null,
              dataSourcePending: true,
              priceSources: [
                {
                  id: "akshare_sina_daily",
                  label: "AkShare 日线（新浪优先）",
                  unlicensed: true,
                  acknowledgedAt: acknowledged,
                  market: "CN",
                },
                {id: "yahoo_daily", label: "雅虎日线", unlicensed: true, market: "US"},
              ],
            },
          }}
        />
      </I18nProvider>,
    );
    const run = screen.getByTestId("confirm-run-start");
    expect(screen.getByTestId("price-source-akshare_sina_daily")).not.toBeChecked();
    expect(run).toBeDisabled();
    expect(run).toHaveAttribute("data-run-blocked", "source");
    expect(screen.getByTestId("confirm-run-blocked-reason")).toHaveTextContent(
      "还没选数据源。先在确认卡上选一个，再开跑。",
    );
    expect(screen.getByTestId("confirm-data-meta")).toHaveTextContent("待选择");
    fireEvent.click(run);
    expect(invoke).not.toHaveBeenCalledWith("confirm_run", expect.anything());
  });

  it("names a finance acronym once when the token and the ticker are the same", () => {
    const ask = {
      blocked: true,
      code: "SYMBOL_ASK_PENDING" as const,
      token: "AI",
      symbol: "AI",
      symbols: [] as string[],
      inferred: [],
      editable: true,
      asks: [{token: "AI", symbol: "AI", kind: "finance" as const}],
    };
    renderCard(ZH, ask);
    const line = screen.getByTestId("symbol-ask").textContent ?? "";
    expect(line).toContain("AI 是美股代码，也是金融缩写。要把它当作标的吗？");
    expect(line).not.toContain("「AI」是美股代码 AI");
    cleanup();
    renderCard(EN, ask);
    expect(screen.getByTestId("symbol-ask")).toHaveTextContent(
      "AI is a US ticker and also a finance abbreviation. Use it as a symbol?",
    );
  });
});
