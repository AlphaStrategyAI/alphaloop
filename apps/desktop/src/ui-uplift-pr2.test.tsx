import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";
import {DraftScreen} from "./screens/ConfirmRunScreen";
import {MethodsScreen} from "./screens/MethodsScreen";
import {createMemoryLlmSettingsPort} from "./settings/llmSettingsPort";
import {SettingsPage} from "./settings/SettingsPage";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi();
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

const draftSettings = {
  thesis: "",
  universe: "美股 · 股票",
  max_effective_hours: "",
  round1_methods: "",
  coverage_floor: "",
};

describe("draft chat structure", () => {
  const view: Extract<DesktopView, {kind: "draft"}> = {
    kind: "draft",
    researchId: "r-draft",
    dialogue: [
      {role: "assistant", text: "暂不支持动量族。请改选策略族："},
      {role: "user", text: "想做 Momentum 美股股票"},
    ],
    familyChipIds: ["low_volatility", "mean_reversion"],
    settings: draftSettings,
  };

  it("keeps the assistant on the left, the user on the right, chips under the thread, and a fixed send", () => {
    render(<App api={api} initialView={view} initialRoute="#/research/r-draft" />);
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-has-aside", "true");
    expect(screen.getByTestId("draft-chat")).toHaveClass("draft-layout");
    const assistant = screen.getByText("暂不支持动量族。请改选策略族：");
    const user = screen.getByText("想做 Momentum 美股股票");
    expect(assistant).toHaveClass("assistant");
    expect(user).toHaveClass("user");
    expect(assistant.compareDocumentPosition(user) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const thread = document.querySelector(".conversation-thread");
    const chips = screen.getByTestId("family-chips");
    expect(thread).toContainElement(chips);
    expect(thread).toContainElement(user);
    expect(user.compareDocumentPosition(chips) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const send = screen.getByTestId("dialogue-send");
    expect(send).toBeDisabled();
    expect(screen.getByTestId("draft-composer")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("dialogue-input"), {target: {value: "低波"}});
    expect(send).toBeEnabled();
  });

  it("shows five locks, a pending clarification, and the confirm action only when all are filled", () => {
    render(<DraftScreen api={api} view={view} />);
    expect(screen.getAllByTestId(/^brief-slot-/)).toHaveLength(5);
    expect(screen.getByTestId("brief-slot-thesis")).toHaveAttribute("data-lock", "pending");
    expect(screen.getByTestId("brief-slot-thesis")).toHaveTextContent("未锁定");
    expect(screen.getByTestId("brief-slot-thesis")).not.toHaveTextContent("待澄清");
    expect(screen.getByTestId("brief-slot-universe")).toHaveAttribute("data-lock", "locked");
    expect(screen.getByTestId("brief-slot-max_effective_hours")).toHaveAttribute("data-lock", "empty");
    expect(screen.getByTestId("draft-lock-progress")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.queryByTestId("draft-go-confirm")).not.toBeInTheDocument();
    cleanup();

    render(
      <DraftScreen
        api={api}
        view={{
          ...view,
          settings: {
            thesis: "低波",
            universe: "美股 · 股票",
            max_effective_hours: "12 小时",
            round1_methods: "换手成本",
            coverage_floor: "至少 1 个标的",
          },
        }}
      />,
    );
    expect(screen.getByTestId("draft-go-confirm")).toHaveTextContent("去确认开跑");
    expect(screen.getByTestId("draft-lock-progress")).toHaveAttribute("aria-valuenow", "5");
  });

  it("keeps English time examples in the time lock and leaves methods unlocked", () => {
    const answered = {
      ...view,
      dialogue: [
        {role: "assistant" as const, text: "How much effective research time is allowed?"},
        {role: "user" as const, text: "30 minutes"},
        {role: "assistant" as const, text: "Which frozen verification methods should the first round use?"},
      ],
      settings: {
        thesis: "Mean reversion on AAPL, a US stock, using daily prices.",
        universe: "美股 · 股票",
        max_effective_hours: "0.5 小时",
        round1_methods: "",
        coverage_floor: "",
      },
    };
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <DraftScreen api={api} view={answered} />
      </I18nProvider>,
    );
    const hours = screen.getByTestId("brief-slot-max_effective_hours");
    const methods = screen.getByTestId("brief-slot-round1_methods");
    expect(hours).toHaveAttribute("data-lock", "locked");
    expect(hours).toHaveTextContent("30 min");
    expect(hours).not.toHaveTextContent("Not locked");
    expect(methods).toHaveAttribute("data-lock", "pending");
    expect(methods).toHaveTextContent("Not locked");
    expect(methods).not.toHaveTextContent("To clarify");
    expect(screen.getByTestId("draft-chat")).toHaveClass("draft-layout");
    unmount();

    render(
      <I18nProvider initial={EN}>
        <DraftScreen
          api={api}
          view={{
            ...answered,
            settings: {...answered.settings, max_effective_hours: "12 小时"},
          }}
        />
      </I18nProvider>,
    );
    expect(screen.getByTestId("brief-slot-max_effective_hours")).toHaveTextContent("12 h");
    const twelve = screen.getByTestId("brief-slot-round1_methods");
    expect(twelve).toHaveAttribute("data-lock", "pending");
    expect(twelve).toHaveTextContent("Not locked");
    expect(twelve).not.toHaveTextContent("To clarify");
  });
});

describe("running structure", () => {
  it("uses an 8px progress track and a rotating phase ring", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 2,
      effective: "12秒",
      effectiveSeconds: 12,
      remainingSeconds: 1788,
      remaining: "29分48秒",
      coverage: "11.6 年",
      rounds: [],
      currentAction: "查资料",
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("effective-quota-track")).toHaveAttribute("data-track-px", "8");
    const ring = screen.getByTestId("version-orbit");
    expect(ring).toHaveAttribute("data-phase-ring", "rotate");
    expect(ring).toHaveAttribute("data-phase-rotate", "1.2s");
    expect(ring).toHaveClass("phase-ring");
    expect(screen.getByTestId("phase-ring-arc")).toBeInTheDocument();
    expect(screen.getByTestId("effective-quota-fill")).toHaveAttribute("data-sheen", "1.6s");
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-has-aside", "true");
    expect(screen.getByTestId("run-status-title")).toHaveTextContent("运行中");
  });
});

describe("methods 40/60", () => {
  it("splits the library and keeps the scorecard after cancel", () => {
    const reviseMethod = vi.fn(async () => undefined);
    const view: Extract<DesktopView, {kind: "methods"}> = {
      kind: "methods",
      selected: "scorecard.market",
      methods: [
        {
          id: "scorecard.market",
          name: "市场计分卡",
          revision: "rev-1",
          description: "用多维指标衡量策略是否达到最低可接受表现。",
          definitionDisplay: "用途：多维指标",
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
        },
        {
          id: "cost",
          name: "换手成本",
          revision: "rev-1",
          description: "成本",
        },
      ],
    };
    render(<MethodsScreen api={minimalDesktopApi({reviseMethod})} view={view} />);
    const layout = screen.getByTestId("methods-layout");
    expect(layout).toHaveAttribute("data-split", "40/60");
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("方法库");
    const selected = screen.getByRole("link", {name: /市场计分卡/});
    expect(selected).toHaveClass("active");
    expect(screen.getByTestId("scorecard-dimensions")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: "编辑为新定义"}));
    const dialog = screen.getByTestId("revise-method-dialog");
    fireEvent.change(dialog.querySelector("textarea")!, {target: {value: "草稿不应留下"}});
    fireEvent.click(screen.getByRole("button", {name: "取消"}));
    expect(reviseMethod).not.toHaveBeenCalled();
    expect(screen.getByTestId("scorecard-dimensions")).toHaveTextContent("夏普比率");
    expect(screen.queryByDisplayValue("草稿不应留下")).not.toBeInTheDocument();
  });
});

describe("glossary structure", () => {
  const view: Extract<DesktopView, {kind: "glossary"}> = {
    kind: "glossary",
    intro: "界面显示名有调整；方法 ID 与修订号不变。",
    entries: [
      {
        id: "pit.consistency",
        term: "时点一致性",
        body: "在不同时间切片上复现。旧称「时间序列一致性」仍可解析。",
      },
      {
        id: "trial_counts",
        term: "试验轮数",
        body: "试验轮数说明。",
      },
    ],
  };

  it("titles the page, searches aliases, and leaves later entries collapsed", () => {
    render(<App api={api} initialView={view} initialRoute="#/glossary" />);
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-has-aside", "false");
    expect(screen.queryByTestId("detail-aside")).not.toBeInTheDocument();
    expect(screen.getByTestId("glossary-page")).toHaveAttribute("data-column-max", "720");
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("术语");
    const first = screen.getByText("时点一致性").closest("details");
    const second = screen.getByText("试验轮数").closest("details");
    expect(first).toHaveAttribute("open");
    expect(second).not.toHaveAttribute("open");
    expect(screen.getByTestId("glossary-former")).toHaveTextContent("曾用名：时间序列一致性");
    fireEvent.change(screen.getByTestId("glossary-search"), {target: {value: "时间序列"}});
    expect(screen.getByText("时点一致性")).toBeInTheDocument();
    expect(screen.queryByText("试验轮数")).not.toBeInTheDocument();
  });
});

describe("settings llm and general structure", () => {
  it("uses a cyan focus ring, two disclosure columns, and three language options", () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/llm" llmPort={createMemoryLlmSettingsPort().port} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("settings-page")).toHaveAttribute("data-has-aside", "false");
    expect(document.querySelector(".llm-form")).toHaveAttribute("data-focus-ring", "cyan");
    expect(screen.getByTestId("llm-optional")).toHaveTextContent("大模型可选");
    expect(screen.getByTestId("llm-columns")).toHaveTextContent("会发送");
    expect(screen.getByTestId("llm-columns")).toHaveTextContent("不会发送");
    expect(screen.queryByText(/必须配置大模型/)).not.toBeInTheDocument();
  });

  it("keeps three language choices and a two-column scope in English", () => {
    render(
      <I18nProvider initial={EN}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    expect(document.querySelector("[data-option-count='3']")?.querySelectorAll("input[type='radio']")).toHaveLength(3);
    const columns = screen.getByTestId("settings-scope-columns");
    expect(columns).toHaveTextContent("Switches");
    expect(columns).toHaveAttribute("data-scope-columns", "2");
    expect(columns).toHaveTextContent("Stays as-is");
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("Settings");
  });

  it("shows the English honesty surface without an aside", () => {
    render(
      <I18nProvider initial={EN}>
        <SettingsPage route="#/settings/data" />
      </I18nProvider>,
    );
    const honesty = screen.getByTestId("honesty-sentences");
    expect(honesty).toHaveTextContent("survivorship bias");
    expect(honesty).toHaveTextContent("point-in-time");
    expect(honesty).toHaveTextContent("EDGAR");
    expect(screen.getAllByText("Unlicensed").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByTestId("data-save")).toBeDisabled();
    expect(screen.getByTestId("data-save-hint")).toHaveTextContent("Check this to save");
    expect(screen.getByTestId("settings-page")).toHaveAttribute("data-has-aside", "false");
  });
});
