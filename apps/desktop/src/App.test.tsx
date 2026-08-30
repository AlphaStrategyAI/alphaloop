import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App, AwaitingConfirmCard, ConfirmRunCard, routeFor } from "./App";
import type { DesktopApi, DesktopView } from "./contracts";

afterEach(() => {
  cleanup();
});

const api: DesktopApi = {
  fetchView: vi.fn(() => new Promise<DesktopView>(() => undefined)),
  createDraft: vi.fn(async () => "r-new"),
  confirmRun: vi.fn(async () => undefined),
  sendDialogue: vi.fn(async () => undefined),
  pauseResearch: vi.fn(async () => undefined),
  resumeResearch: vi.fn(async () => undefined),
  confirmModification: vi.fn(async () => undefined),
  extendResearch: vi.fn(async () => undefined),
  deleteResearch: vi.fn(async () => undefined),
  resolveConfirm: vi.fn(async () => undefined),
  exportArtifact: vi.fn(async () => undefined),
  reverify: vi.fn(async () => undefined),
  reviseMethod: vi.fn(async () => undefined),
};

const settings = {
  thesis: "美股低波动回归",
  universe: "美股 · 股票",
  max_effective_hours: "12 小时",
  round1_methods: "走样检验 · 样本外稳定 · 拥挤度 · 换手成本",
  coverage_floor: "至少 10 年，缺失不超过 5%",
} as const;

const views: DesktopView[] = [
  {
    kind: "research_list",
    awaiting: {id: "r-wait", title: "美股低波动量价回归", status: "awaiting_confirm"},
    rows: [
      {id: "r-run", title: "中债期限利差交换", status: "running"},
      {id: "r-draft", title: "沪深300波动收缩", status: "draft"},
      {id: "r-pause", title: "美债收益率曲线", status: "paused"},
      {id: "r-done", title: "行业动量", status: "completed"},
      {id: "r-end", title: "转债估值修复", status: "ended"},
    ],
  },
  {kind: "draft", researchId: "r-1", messages: ["我想研究美股低波动回归"], settings},
  {kind: "confirm_run", researchId: "r-1", settings},
  {
    kind: "running",
    researchId: "r-1",
    status: "running",
    version: 2,
    effective: "3h12 / 12h",
    coverage: "覆盖仍在底线之上",
    rounds: ["样本外走样，准备加拥挤度过滤", "量价回归，三项验证"],
  },
  {
    kind: "awaiting_confirm",
    researchId: "r-1",
    version: 2,
    proposed: "信号从量价回归改成回归 + 拥挤度过滤",
    reason: "第 6 轮样本外走样，单纯回归在拥挤月份失效",
    effect: "确认后开出第 3 版；验证方法不变，经济逻辑改变",
  },
  {
    kind: "completed",
    researchId: "r-1",
    status: "completed",
    title: "低波动量价回归 + 拥挤度过滤",
    selectedRoundId: "r-export-v1-r1",
    selectedMethodId: "overfit.walk",
    eligibility: {
      allMethodsPassed: true,
      noPendingConfirm: true,
      reverifiesPassed: true,
    },
  },
  {
    kind: "methods",
    selected: "overfit.walk",
    methods: [
      {id: "overfit.walk", name: "走样检验", revision: "walk-v1", description: "检验策略样本外是否走样。"},
      {id: "stability.oos", name: "样本外稳定", revision: "stability-v1", description: "至少三个样本外区间。"},
    ],
  },
];

describe("Night desktop contract", () => {
  it.each(views)("renders the $kind Figma view in one fixed shell", (view) => {
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", view.kind);
    expect(screen.getByTestId("rail")).toBeInTheDocument();
    expect(screen.getByLabelText("alphaloop")).toBeInTheDocument();
  });

  it("keeps awaiting-confirm as a primary list card before ordinary rows", () => {
    render(<App api={api} initialView={views[0]} />);
    const articles = screen.getAllByRole("article");
    expect(articles[0]).toHaveAttribute("data-kind", "awaiting-primary");
    expect(screen.getAllByTestId("research-row")).toHaveLength(5);
  });

  it("shows exactly five read-only setting slots in draft", () => {
    render(<App api={api} initialView={views[1]} />);
    expect(screen.getAllByTestId("brief-slot")).toHaveLength(5);
    expect(screen.getByPlaceholderText("把方向说清楚，不用填表。")).toBeInTheDocument();
  });

  it("uses two distinct non-modal confirmation cards", () => {
    const {rerender} = render(<ConfirmRunCard api={api} view={views[2] as Extract<DesktopView, {kind: "confirm_run"}>} />);
    expect(screen.getByTestId("confirm-run-card")).not.toHaveAttribute("role", "dialog");
    rerender(<AwaitingConfirmCard api={api} view={views[4] as Extract<DesktopView, {kind: "awaiting_confirm"}>} />);
    expect(screen.getByTestId("awaiting-confirm-card")).not.toHaveAttribute("role", "dialog");
    expect(screen.queryByTestId("confirm-run-card")).not.toBeInTheDocument();
  });

  it("offers all three awaiting-confirm decisions without a default", () => {
    render(<App api={api} initialView={views[4]} />);
    fireEvent.click(screen.getByRole("button", {name: "同意，开新的一版"}));
    fireEvent.click(screen.getByRole("button", {name: "不同意，维持原逻辑继续"}));
    fireEvent.click(screen.getByRole("button", {name: "暂停，我自己改"}));
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(1, "r-1", "approve_new_version");
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(2, "r-1", "reject_keep_logic");
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(3, "r-1", "pause_and_edit");
  });

  it("has no order or account action on any screen", () => {
    for (const view of views) {
      const rendered = render(<App api={api} initialView={view} />);
      const actions = screen.queryAllByRole("button").map((button) => button.textContent ?? "").join(" ");
      expect(actions).not.toMatch(/下单|买入|卖出|连接账户|开始交易/);
      rendered.unmount();
    }
  });

  it("routes every research state through one research route", () => {
    expect(routeFor(views[1])).toBe("#/research/r-1");
    expect(routeFor(views[2])).toBe("#/research/r-1");
    expect(routeFor(views[3])).toBe("#/research/r-1");
    expect(routeFor(views[4])).toBe("#/research/r-1");
    expect(routeFor(views[5])).toBe("#/research/r-1");
    expect(routeFor(views[0])).toBe("#/research");
    expect(routeFor(views[6])).toBe("#/methods/overfit.walk");
  });
});
