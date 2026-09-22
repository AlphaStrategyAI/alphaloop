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
  resolveConfirm: vi.fn(async (_researchId: string, _decision: string, _whoPays?: string) => undefined),
  exportArtifact: vi.fn(async () => undefined),
  reverify: vi.fn(async () => undefined),
  reviseMethod: vi.fn(async () => undefined),
  createMethod: vi.fn(async () => undefined),
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
    awaiting: {
      id: "r-wait",
      title: "美股低波动量价回归",
      status: "awaiting_confirm",
      universeLabel: "美股 · 股票",
      createdAt: "2026-08-28T12:00:00+00:00",
      updatedAt: "2026-08-28T14:00:00+00:00",
    },
    rows: [
      {id: "r-run", title: "中债期限利差交换", status: "running", universeLabel: "A股 · 债券"},
      {id: "r-draft", title: "沪深300波动收缩", status: "draft", universeLabel: "A股 · 股票"},
      {id: "r-pause", title: "美债收益率曲线", status: "paused", universeLabel: "美股 · 债券"},
      {id: "r-done", title: "行业动量", status: "completed", universeLabel: "A股 · 股票"},
      {id: "r-end", title: "转债估值修复", status: "ended", universeLabel: "A股 · 债券"},
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
    rounds: [
      {
        roundId: "round-2",
        number: 2,
        logicStatement: {statement: "样本外走样，准备加拥挤度过滤", changedFromPrior: true, changeDescription: "加入拥挤度指标", baselineVersion: 1},
        implementationDelta: {researchMethodChanges: [], modelChanges: ["crowd_filter"], paramChanges: [["threshold", "0.8", "0.6"]]},
        trialCounters: {candidatesEvaluated: 15, candidatesPassed: 3, conclusionAttemptNumber: 2},
        verificationPassed: true,
      },
      {
        roundId: "round-1",
        number: 1,
        logicStatement: {statement: "量价回归，三项验证", changedFromPrior: false, baselineVersion: 1},
        implementationDelta: {researchMethodChanges: [], modelChanges: [], paramChanges: []},
        trialCounters: {candidatesEvaluated: 10, candidatesPassed: 2, conclusionAttemptNumber: 1},
        verificationPassed: true,
      },
    ],
  },
  {
    kind: "awaiting_confirm",
    researchId: "r-1",
    version: 2,
    confirmKind: "economic",
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
      pitExecutedAndPassed: true,
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

  it("lets the awaiting primary card enter and delete like ordinary rows", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<App api={api} initialView={views[0]} />);
    const card = screen.getAllByRole("article")[0];
    expect(card.querySelector('a[href="#/research/r-wait"]')).not.toBeNull();
    const enter = screen.getAllByRole("link", {name: "进入"})[0];
    expect(enter).toHaveAttribute("href", "#/research/r-wait");
    fireEvent.click(card.querySelectorAll("button")[0]);
    expect(confirm).toHaveBeenCalled();
    expect(api.deleteResearch).toHaveBeenCalledWith("r-wait");
    confirm.mockRestore();
  });

  it("titles coverage awaiting cards differently from economic ones", () => {
    const {rerender} = render(
      <AwaitingConfirmCard api={api} view={views[4] as Extract<DesktopView, {kind: "awaiting_confirm"}>} />,
    );
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("经济逻辑要改了");
    rerender(
      <AwaitingConfirmCard
        api={api}
        view={{
          kind: "awaiting_confirm",
          researchId: "r-1",
          version: 2,
          confirmKind: "coverage",
          proposed: "覆盖将低于认下的底线",
          reason: "可用历史不够十年",
          effect: "确认后改写覆盖底线并开新版本",
        }}
      />,
    );
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("数据覆盖要跌破底线");
  });

  it("offers §4.6 coverage-specific choices when confirmKind is coverage (T6)", () => {
    const resolveConfirm = vi.fn(async () => undefined);
    render(
      <AwaitingConfirmCard
        api={{...api, resolveConfirm}}
        view={{
          kind: "awaiting_confirm",
          researchId: "r-1",
          version: 2,
          confirmKind: "coverage",
          proposed: "覆盖将低于认下的底线",
          reason: "可用历史不够十年",
          effect: "确认后改写覆盖底线并开新版本",
        }}
      />,
    );
    expect(screen.getByTestId("coverage-decisions")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: "认下更低底线并开新版"}));
    expect(resolveConfirm).toHaveBeenCalledWith("r-1", "accept_lower_floor");
    fireEvent.click(screen.getByRole("button", {name: "提供本机材料补充覆盖"}));
    expect(resolveConfirm).toHaveBeenCalledWith("r-1", "supply_local_materials");
    fireEvent.click(screen.getByRole("button", {name: "缩小研究范围"}));
    expect(resolveConfirm).toHaveBeenCalledWith("r-1", "redefine_scope");
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
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(1, "r-1", "approve_new_version", undefined);
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

  it("filters the research list by status and shows universe plus timestamps", async () => {
    const view = views[0];
    render(<App api={api} initialView={view} />);
    expect(screen.getByText("美股 · 股票")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: "已暂停"}));
    expect(screen.getByText("美债收益率曲线")).toBeInTheDocument();
    expect(screen.queryByText("沪深300波动收缩")).not.toBeInTheDocument();
  });

  it("shows overturned prior exports on a completed research that failed reverify", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "completed",
          researchId: "r-1",
          status: "completed",
          title: "美股低波动回归",
          selectedRoundId: "round-1",
          selectedMethodId: "overfit.walk",
          eligibility: {allMethodsPassed: true, noPendingConfirm: true, reverifiesPassed: false, pitExecutedAndPassed: true},
          overturnedExports: true,
          currentAction: "idle",
        }}
      />,
    );
    expect(screen.getByText("此前导出的策略包所依据的验证已被推翻")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "导出策略包"})).toBeDisabled();
  });

  it("shows Scorecard dimensions in method detail (B6)", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "methods",
          selected: "scorecard.market",
          methods: [{
            id: "scorecard.market",
            name: "市场计分卡",
            revision: "scorecard-v1",
            description: "市场表现计分卡",
            usageCount: 5,
            source: "preset",
            category: "计分卡",
            dimensions: [
              {kind: "predictive_power", name: "夏普比率", description: "样本外夏普比率下限", passThreshold: 0, comparison: "gt", failureDisplay: "夏普不高于基准"},
              {kind: "stability", name: "最大回撤", description: "回撤上限", passThreshold: -0.25, comparison: "gte", failureDisplay: "回撤过大"},
            ],
          }],
        }}
      />,
    );
    expect(screen.getByText("计分卡")).toBeInTheDocument();
    expect(screen.getByTestId("scorecard-dimensions")).toBeInTheDocument();
    expect(screen.getByText("夏普比率")).toBeInTheDocument();
    expect(screen.getByText("最大回撤")).toBeInTheDocument();
    expect(screen.getByText("夏普不高于基准")).toBeInTheDocument();
  });

  it("can pre-create a method from the library screen", async () => {
    const createMethod = vi.fn(async () => undefined);
    render(
      <App
        api={{...api, createMethod}}
        initialView={{kind: "methods", methods: []}}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText("新方法名称"), {target: {value: "换手冲击"}});
    fireEvent.change(screen.getByPlaceholderText("方法定义"), {target: {value: "换手超过阈值则失败"}});
    fireEvent.click(screen.getByRole("button", {name: "预先新建方法"}));
    expect(createMethod).toHaveBeenCalledWith("换手冲击", "换手超过阈值则失败");
  });

  it("keeps overturned banner but enables strategy-pack export when eligibility checks pass", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "completed",
          researchId: "r-1",
          status: "completed",
          title: "美股低波动回归",
          selectedRoundId: "round-1",
          selectedMethodId: "overfit.walk",
          eligibility: {allMethodsPassed: true, noPendingConfirm: true, reverifiesPassed: true, pitExecutedAndPassed: true},
          overturnedExports: true,
          currentAction: "idle",
        }}
      />,
    );
    expect(screen.getByText("此前导出的策略包所依据的验证已被推翻")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "导出策略包"})).toBeEnabled();
  });

  it("shows four eligibility gates including PIT and disables export when PIT fails (B1)", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "completed",
          researchId: "r-1",
          status: "completed",
          title: "低波动回归",
          selectedRoundId: "round-1",
          selectedMethodId: "overfit.walk",
          eligibility: {allMethodsPassed: true, noPendingConfirm: true, reverifiesPassed: true, pitExecutedAndPassed: false},
          currentAction: "idle",
        }}
      />,
    );
    const eligibilityDiv = document.querySelector(".eligibility");
    expect(eligibilityDiv).toBeInTheDocument();
    expect(eligibilityDiv?.children).toHaveLength(4);
    expect(eligibilityDiv?.textContent).toContain("时点一致性已执行且通过");
    expect(eligibilityDiv?.textContent).toContain("○ 时点一致性已执行且通过");
    expect(screen.getByRole("button", {name: "导出策略包"})).toBeDisabled();
  });

  it("renders round cards with two-column layout and trial counters (B2/B3)", () => {
    render(<App api={api} initialView={views[3]} />);
    const roundCards = screen.getAllByTestId("round-card");
    expect(roundCards).toHaveLength(2);
    expect(screen.getAllByText("逻辑陈述")).toHaveLength(2);
    expect(screen.getAllByText("实现与参数")).toHaveLength(2);
    expect(screen.getByText("候选 15")).toBeInTheDocument();
    expect(screen.getByText("通过 3")).toBeInTheDocument();
    expect(screen.getByText("第 2 次尝试")).toBeInTheDocument();
    expect(screen.getByText("threshold: 0.8 → 0.6")).toBeInTheDocument();
  });

  it("renders anomaly checklist when anomalies are detected (B5)", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "completed",
          researchId: "r-1",
          status: "completed",
          title: "低波动回归",
          selectedRoundId: "round-1",
          selectedMethodId: "overfit.walk",
          eligibility: {allMethodsPassed: true, noPendingConfirm: true, reverifiesPassed: true, pitExecutedAndPassed: true},
          currentAction: "idle",
          anomaly: {
            indicators: ["sharpe_outlier", "high_trial_count"],
            expandEvidenceFirst: true,
            tone: "checklist",
            baseline: {kind: "version_1_logic", sharpe: 0.5, trialCount: 5},
          },
        }}
      />,
    );
    expect(screen.getByTestId("anomaly-checklist")).toBeInTheDocument();
    expect(screen.getByText("结果需要额外审视")).toBeInTheDocument();
    expect(screen.getByText("夏普比率相对基线异常偏高")).toBeInTheDocument();
    expect(screen.getByText("尝试次数相对基线异常多")).toBeInTheDocument();
    expect(screen.getByText(/基线夏普 0.5/)).toBeInTheDocument();
  });

  it("shows who-pays input and evidence refs in awaiting-confirm card (B4)", () => {
    const resolveConfirm = vi.fn(async () => undefined);
    render(
      <AwaitingConfirmCard
        api={{...api, resolveConfirm}}
        view={{
          kind: "awaiting_confirm",
          researchId: "r-1",
          version: 2,
          confirmKind: "economic",
          proposed: "信号改成回归 + 拥挤度过滤",
          reason: "样本外走样",
          effect: "开出第 3 版",
          whyChange: [
            {recordId: "attempt-123", recordedAt: "2026-08-28T10:00:00Z", kind: "attempt", summary: "候选策略表现"},
            {recordId: "round-1", recordedAt: "2026-08-28T09:00:00Z", kind: "round"},
          ],
          whoPaysOptional: null,
          createdAt: "2026-08-28T12:00:00Z",
          requestId: "req-001",
        }}
      />,
    );
    expect(screen.getByText("证据依据")).toBeInTheDocument();
    expect(screen.getByText("attempt")).toBeInTheDocument();
    expect(screen.getByText("attempt-123")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("不填则记录为「未作答」")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("不填则记录为「未作答」"), {target: {value: "用户自担"}});
    fireEvent.click(screen.getByRole("button", {name: "同意，开新的一版"}));
    expect(resolveConfirm).toHaveBeenCalledWith("r-1", "approve_new_version", "用户自担");
  });
});
