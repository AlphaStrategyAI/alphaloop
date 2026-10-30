import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App, ConfirmRunCard} from "./App";
import type {DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";
import {DraftScreen} from "./screens/ConfirmRunScreen";
import {MethodDetail} from "./screens/MethodsScreen";
import {RouteLoading} from "./screens/RouteLoading";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const api = minimalDesktopApi();
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

const scorecard = {
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
      comparison: "gt" as const,
      comparisonLabel: "大于",
      failureDisplay: "夏普不高于基准",
    },
  ],
};

function mockReducedMotion(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation(() => ({
      matches,
      media: "(prefers-reduced-motion: reduce)",
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
      onchange: null,
    })),
  });
}

describe("running motion", () => {
  it("leaves a paused ring static and skips the sheen", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "paused",
      version: 2,
      effective: "12秒",
      effectiveSeconds: 12,
      remainingSeconds: 1788,
      remaining: "29分48秒",
      coverage: "11.6 年",
      rounds: [],
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("version-orbit")).toHaveAttribute("data-phase-ring", "static");
    expect(screen.queryByTestId("phase-ring-arc")).not.toBeInTheDocument();
    expect(screen.getByTestId("effective-quota-fill")).not.toHaveAttribute("data-sheen");
    expect(screen.getByTestId("effective-quota-fill")).not.toHaveClass("quota-sheen");
  });
});

describe("gate motion", () => {
  it("staggers gate lights and flashes the failed pill", () => {
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
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    const gates = screen.getByTestId("completed-gate-pills");
    expect(gates).toHaveAttribute("data-gate-stagger", "90");
    const pills = gates.querySelectorAll(".gate-pill");
    expect(pills).toHaveLength(4);
    expect(pills[0]).toHaveAttribute("data-gate-flash", "150");
    expect(pills[0]).toHaveClass("gate-pill--fail");
    expect(pills[1]).not.toHaveAttribute("data-gate-flash");
    expect(screen.getByTestId("host-status")).toHaveAttribute("data-rail-tone", "stop");
    expect(screen.getByTestId("rail-status-label")).toHaveTextContent("完成");
  });
});

describe("send and start motion", () => {
  const draft: Extract<DesktopView, {kind: "draft"}> = {
    kind: "draft",
    researchId: "r-draft",
    dialogue: [
      {role: "assistant", text: "请补充原理。"},
      {role: "user", text: "先说一句"},
    ],
    settings: {
      thesis: "",
      universe: "",
      max_effective_hours: "",
      round1_methods: "",
      coverage_floor: "",
    },
  };

  it("pulses send and raises only the new user bubble", () => {
    const sendDialogue = vi.fn(async () => undefined);
    const {rerender} = render(<DraftScreen api={minimalDesktopApi({sendDialogue})} view={draft} />);
    const send = screen.getByTestId("dialogue-send");
    expect(send).toHaveAttribute("data-send-motion", "180");
    expect(screen.getByText("先说一句")).not.toHaveClass("message-rise");
    fireEvent.change(screen.getByTestId("dialogue-input"), {target: {value: "低波"}});
    fireEvent.click(send);
    expect(sendDialogue).toHaveBeenCalledWith("r-draft", "低波");
    expect(send).toHaveClass("send-pulse");
    rerender(
      <DraftScreen
        api={minimalDesktopApi({sendDialogue})}
        view={{...draft, dialogue: [...draft.dialogue, {role: "user", text: "低波"}]}}
      />,
    );
    const turns = screen.getAllByTestId("dialogue-turn");
    const risen = turns[turns.length - 1];
    expect(risen).toHaveTextContent("低波");
    expect(risen).toHaveClass("message-rise");
    expect(risen).toHaveAttribute("data-bubble-motion", "220");
    expect(screen.getByText("先说一句")).not.toHaveClass("message-rise");
  });

  it("skips send travel when reduced motion is requested", () => {
    mockReducedMotion(true);
    const {rerender} = render(<DraftScreen api={api} view={draft} />);
    fireEvent.change(screen.getByTestId("dialogue-input"), {target: {value: "低波"}});
    fireEvent.click(screen.getByTestId("dialogue-send"));
    expect(screen.getByTestId("dialogue-send")).not.toHaveClass("send-pulse");
    rerender(
      <DraftScreen
        api={api}
        view={{...draft, dialogue: [...draft.dialogue, {role: "user", text: "低波"}]}}
      />,
    );
    const turns = screen.getAllByTestId("dialogue-turn");
    expect(turns[turns.length - 1]).toHaveTextContent("低波");
    expect(turns[turns.length - 1]).not.toHaveClass("message-rise");
  });

  it("marks the run button for an 80ms press", () => {
    render(
      <ConfirmRunCard
        api={api}
        view={{
          kind: "confirm_run",
          researchId: "r-1",
          dialogue: [],
          chatEnabled: false,
          settings: {
            thesis: "均值回归",
            universe: "美股 · 股票",
            max_effective_hours: "4 小时",
            round1_methods: "分段稳健性检验",
            coverage_floor: "至少 25 个标的",
          },
        }}
      />,
    );
    expect(screen.getByTestId("confirm-run-start")).toHaveAttribute("data-run-motion", "80");
    expect(screen.getByTestId("brief-slot-thesis")).toBeInTheDocument();
  });
});

describe("rail research status", () => {
  it("shows Run in English without CJK on a running detail", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "1h",
      coverage: "ok",
      rounds: [],
    };
    render(
      <I18nProvider initial={EN}>
        <App api={api} initialView={view} initialRoute="#/research/r-1" />
      </I18nProvider>,
    );
    const label = screen.getByTestId("rail-status-label");
    expect(label).toHaveTextContent("Run");
    expect(label.textContent ?? "").not.toMatch(/[\u4e00-\u9fff]/);
    expect(screen.getByTestId("host-status")).toHaveAttribute("data-rail-tone", "run");
    expect(screen.getByTestId("run-status-title")).toHaveTextContent("Running");
  });
});

describe("methods edit dialog", () => {
  it("closes from the corner control and from Escape without dropping the scorecard", () => {
    const reviseMethod = vi.fn(async () => undefined);
    render(<MethodDetail api={minimalDesktopApi({reviseMethod})} method={scorecard} />);
    fireEvent.click(screen.getByRole("button", {name: "编辑为新定义"}));
    fireEvent.change(screen.getByRole("textbox"), {target: {value: "草稿不应留下"}});
    fireEvent.click(screen.getByTestId("revise-method-close"));
    expect(reviseMethod).not.toHaveBeenCalled();
    expect(screen.queryByTestId("revise-method-dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("scorecard-dimensions")).toHaveTextContent("夏普比率");

    fireEvent.click(screen.getByRole("button", {name: "编辑为新定义"}));
    fireEvent.change(screen.getByRole("textbox"), {target: {value: "第二次草稿"}});
    fireEvent.keyDown(window, {key: "Escape"});
    expect(screen.queryByTestId("revise-method-dialog")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("第二次草稿")).not.toBeInTheDocument();
    expect(screen.getByTestId("scorecard-dimensions")).toBeInTheDocument();
  });
});

describe("empty and loading skeletons", () => {
  it("shows one empty sentence beside the existing new-research button", () => {
    render(<App api={api} initialView={{kind: "research_list", rows: []}} initialRoute="#/research" />);
    expect(screen.getByTestId("research-list-empty")).toHaveTextContent("还没有研究。从新建研究开始。");
    expect(screen.getByTestId("new-research-button")).toBeInTheDocument();
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-has-aside", "false");
  });

  it("uses a list skeleton on the index and a detail skeleton on a research route", () => {
    const {rerender} = render(<RouteLoading route="#/research" />);
    expect(screen.getByTestId("route-loading")).toHaveAttribute("data-skeleton", "list");
    expect(screen.getByText("加载中…")).toBeInTheDocument();
    expect(document.querySelectorAll(".skeleton-bar--row")).toHaveLength(3);
    rerender(<RouteLoading route="#/research/r-1" />);
    expect(screen.getByTestId("route-loading")).toHaveAttribute("data-skeleton", "detail");
    expect(document.querySelector(".skeleton-bar--card")).toBeInTheDocument();
  });
});
