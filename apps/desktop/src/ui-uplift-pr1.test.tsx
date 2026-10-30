import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopView, ValidationMethod} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";
import {ASIDE_WIDTH, MAIN_MIN_WIDTH, RAIL_WIDTH, shellHasAside} from "./layoutShell";
import {MethodDetail} from "./screens/MethodsScreen";
import {SettingsPage} from "./settings/SettingsPage";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi();

const scorecard: ValidationMethod = {
  id: "scorecard.market",
  name: "市场计分卡",
  revision: "rev-1",
  description: "用多维指标衡量策略是否达到最低可接受表现。",
  definitionDisplay: "用途：用多维指标衡量策略是否达到最低可接受表现。\n样本外夏普下限（不含等于）：0",
  dimensions: [
    {
      kind: "predictive_power",
      kindLabel: "预测力",
      name: "夏普比率",
      description: "样本外夏普比率下限",
      passThreshold: 0,
      comparison: "gt",
      comparisonLabel: "大于",
      failureDisplay: "夏普不高于基准",
    },
  ],
};

describe("uplift shell", () => {
  it("keeps the rail at 72 and withholds the aside on list, glossary, and settings", () => {
    expect(RAIL_WIDTH).toBe(72);
    expect(ASIDE_WIDTH).toBe(320);
    expect(MAIN_MIN_WIDTH).toBe(720);
    expect(shellHasAside("#/research", "research_list")).toBe(false);
    expect(shellHasAside("#/glossary", "glossary")).toBe(false);
    expect(shellHasAside("#/settings/data", "research_list")).toBe(false);
    expect(shellHasAside("#/methods", "methods")).toBe(false);
    expect(shellHasAside("#/research/r-1", "running")).toBe(true);
    expect(shellHasAside("#/research/r-1", "completed")).toBe(true);
    expect(shellHasAside("#/research/r-1", "draft")).toBe(true);
    expect(shellHasAside("#/research/r-1", "confirm_run")).toBe(false);

    render(<App api={api} initialView={{kind: "research_list", rows: []}} initialRoute="#/research" />);
    const shell = screen.getByTestId("night-shell");
    expect(shell).toHaveAttribute("data-rail-width", "72");
    expect(shell).toHaveAttribute("data-main-min", "720");
    expect(shell).toHaveAttribute("data-has-aside", "false");
    expect(screen.queryByTestId("detail-aside")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("alpha策略研究列表");
  });

  it("uses the English list title in sentence case", () => {
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <App api={api} initialView={{kind: "research_list", rows: []}} initialRoute="#/research" />
      </I18nProvider>,
    );
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("Alpha strategy research list");
  });
});

describe("status single truth", () => {
  const paused: DesktopView = {
    kind: "running",
    researchId: "r-1",
    status: "paused",
    version: 2,
    effective: "12秒",
    coverage: "11.6 年",
    rounds: [],
    currentAction: "查资料",
    lastError: {
      code: "DATA_SYMBOLS_EMPTY",
      message: "未选择任何标的，无法加载行情。请在确认开跑前锁定具体代码。",
      count: 1,
    },
  };

  it("uses the same paused copy on the title and pill, and a two-character hold label on the rail", () => {
    render(<App api={api} initialView={paused} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("run-status-title")).toHaveTextContent("已暂停");
    expect(screen.getByTestId("run-status-title")).toHaveAttribute("data-status", "paused");
    expect(screen.getByTestId("list-status-pill")).toHaveTextContent("已暂停");
    expect(screen.getByTestId("rail-status-label")).toHaveTextContent("暂停");
    expect(screen.getByTestId("rail-status-label")).not.toHaveTextContent("已暂停");
    expect(screen.getByTestId("host-status")).toHaveAttribute("data-rail-tone", "hold");
    expect(screen.getByTestId("host-status")).toHaveClass("paused");
    expect(screen.getByTestId("running-screen").textContent).not.toMatch(/运行中/);
    const warning = screen.getByTestId("missing-ticker-warning");
    expect(warning).toContainElement(screen.getByTestId("go-set-tickers"));
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-has-aside", "true");
    expect(screen.getByTestId("detail-aside")).toBeInTheDocument();
  });

  it("submits a symbol from the missing-ticker warning", () => {
    const setResearchSymbol = vi.fn(async () => undefined);
    render(
      <App
        api={minimalDesktopApi({setResearchSymbol})}
        initialView={paused}
        initialRoute="#/research/r-1"
      />,
    );
    fireEvent.click(screen.getByTestId("go-set-tickers"));
    fireEvent.change(screen.getByTestId("paused-symbol-input"), {target: {value: "AAPL"}});
    fireEvent.submit(screen.getByTestId("paused-symbol-input").closest("form")!);
    expect(setResearchSymbol).toHaveBeenCalledWith("r-1", "AAPL");
  });
});

describe("danger confirm", () => {
  it("focuses cancel and paints delete as stop, not cyan", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "research_list",
          rows: [{id: "r-1", title: "均值回归", status: "ended"}],
        }}
        initialRoute="#/research"
      />,
    );
    expect(screen.getByTestId("research-row-more")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("research-row-more"));
    fireEvent.click(screen.getByTestId("delete-research"));
    const dialog = screen.getByTestId("in-app-confirm");
    expect(dialog).toHaveAttribute("data-dim", "0.5");
    const accept = screen.getByTestId("in-app-confirm-accept");
    expect(accept).toHaveClass("danger-button");
    expect(accept).not.toHaveClass("cyan-button");
    expect(document.activeElement).toHaveAttribute("data-dialog-cancel");
    fireEvent.keyDown(accept, {key: "Enter"});
    expect(screen.getByTestId("in-app-confirm")).toBeInTheDocument();
  });
});

describe("settings data honesty", () => {
  it("disables save until the unlicensed acknowledgement is checked", () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/data" />
      </I18nProvider>,
    );
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("设置");
    expect(screen.queryByText("#/settings")).not.toBeInTheDocument();
    const honesty = screen.getByTestId("honesty-sentences");
    expect(honesty).toHaveTextContent("两个大市值池都是名单日的成分，不是时点成分；回看更早的历史含幸存者偏差。");
    expect(honesty).toHaveTextContent("只有把池子定义成某个指数时，才会显示「缺时点成分」。");
    expect(honesty).toHaveTextContent("EDGAR 是否会覆盖旧值尚未确认，基本面的 PIT 检查可能不通过。");
    expect(screen.getAllByText("未经许可").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByTestId("settings-later")).toHaveTextContent("本地文件导入将在 M2 提供。");
    expect(screen.getByText("Sharadar")).toBeInTheDocument();
    expect(screen.getAllByText("尚未对接").length).toBeGreaterThanOrEqual(5);
    const save = screen.getByTestId("data-save");
    expect(save).toBeDisabled();
    expect(screen.getByTestId("data-save-hint")).toHaveTextContent("勾选后可保存");
    fireEvent.click(save);
    expect(screen.queryByTestId("data-saved")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("data-consent"));
    expect(save).toBeEnabled();
    fireEvent.click(save);
    expect(screen.getByTestId("data-saved")).toBeInTheDocument();
  });

  it("puts the default badge on the active language only", () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    expect(screen.getByTestId("ui-language-option-zh").querySelector(".settings-badge")).toHaveTextContent("默认");
    expect(screen.getByTestId("ui-language-option-system").querySelector(".settings-badge")).toBeNull();
  });

  it("keeps settings tabs in chrome outside the scrolling body so clicks are not intercepted", () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    const chrome = screen.getByTestId("settings-chrome");
    const body = screen.getByTestId("settings-body");
    const tab = screen.getByTestId("settings-tab-data");
    const option = screen.getByTestId("ui-language-option-en");
    expect(chrome).toContainElement(tab);
    expect(body).toContainElement(option);
    expect(chrome).not.toContainElement(option);
    expect(body).not.toContainElement(tab);
    expect(option.closest(".settings-chrome")).toBeNull();
  });
});

describe("completed gates before numbers", () => {
  it("places failed gates above title-tier metrics", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "均值回归",
      selectedRoundId: "round-1",
      selectedMethodId: "m1",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      metrics: {excessAnn: -0.055, maxDrawdown: -0.267},
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("completed-failed-eyebrow")).toHaveTextContent("已完成 · 未通过门禁");
    expect(screen.getByTestId("completed-failed-eyebrow").textContent).not.toMatch(/COMPLETED/);
    const gates = screen.getByTestId("completed-gate-pills");
    const metrics = screen.getByTestId("completed-metrics");
    expect(gates.compareDocumentPosition(metrics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(metrics).toHaveAttribute("data-metrics-tier", "title");
  });
});

describe("methods cancel keeps the scorecard", () => {
  it("discards the draft and keeps the table after cancel", () => {
    const reviseMethod = vi.fn(async () => undefined);
    const {rerender} = render(<MethodDetail api={minimalDesktopApi({reviseMethod})} method={scorecard} />);
    expect(screen.getByTestId("scorecard-dimensions")).toHaveTextContent("夏普比率");
    fireEvent.click(screen.getByRole("button", {name: "编辑为新定义"}));
    const field = screen.getByRole("textbox");
    fireEvent.change(field, {target: {value: "草稿正文，不应留下"}});
    fireEvent.click(screen.getByRole("button", {name: "取消"}));
    expect(reviseMethod).not.toHaveBeenCalled();
    expect(screen.queryByDisplayValue("草稿正文，不应留下")).not.toBeInTheDocument();
    expect(screen.getByTestId("method-definition-display")).not.toHaveTextContent("草稿正文");
    expect(screen.getByTestId("scorecard-dimensions")).toBeInTheDocument();
    rerender(
      <MethodDetail
        api={minimalDesktopApi({reviseMethod})}
        method={{...scorecard, dimensions: []}}
      />,
    );
    expect(screen.getByTestId("scorecard-dimensions")).toHaveTextContent("夏普比率");
  });
});
