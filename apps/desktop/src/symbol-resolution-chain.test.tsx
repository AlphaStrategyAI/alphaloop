/**
 * Call chain: confirm card → bindDesktopApi → Tauri invoke payload.
 * A dropped argument here is how a green unit test still shipped a dead button.
 */
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
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
) {
  const invoke = vi.fn(async () => undefined);
  const raw = createTauriDesktopApi(invoke as unknown as DesktopInvoke);
  const bound = bindDesktopApi(raw, {
    onError: vi.fn(),
    refresh: vi.fn(async () => undefined),
  });
  render(
    <I18nProvider initial={language}>
      <ConfirmRunCard api={bound} view={viewWith(resolution)} />
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
});
