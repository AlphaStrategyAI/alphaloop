import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App, AwaitingConfirmCard, ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";
import {RUN_START_RITUAL_MS} from "./runStartRitual";

function mockMatchMedia(matches: boolean) {
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

afterEach(() => cleanup());

const settings = {
  thesis: "关注 600519.SH",
  universe: "A股",
  max_effective_hours: "12h",
  round1_methods: "分段稳健性检验",
  coverage_floor: "8年",
};

const api = minimalDesktopApi({});

describe("Tech Pulse UI", () => {
  it("renders v2 brand mark in the sidebar", () => {
    const view: DesktopView = {kind: "research_list", rows: []};
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("brand-mark").querySelector("img")).toBeTruthy();
  });

  it("renders list workshop chrome", () => {
    render(<App api={api} initialView={{kind: "research_list", rows: []}} />);
    expect(screen.getByText("alpha策略研究列表")).toBeInTheDocument();
    expect(screen.getByText(/一条对话/)).toBeInTheDocument();
    expect(screen.getByTestId("new-research-button")).toHaveTextContent("+");
    expect(screen.getByTestId("new-research-button")).toHaveTextContent("新建研究");
  });

  it("renders bare rail status without glass chip styles", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "1h / 12h",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    const host = screen.getByTestId("host-status");
    expect(host).toHaveClass("rail-status");
  });

  it("shows sidebar status dot copy and list status pills", () => {
    render(
      <App
        api={api}
        initialView={{
          kind: "research_list",
          awaiting: {
            id: "r-w",
            title: "等待拍板",
            status: "awaiting_confirm",
          },
          rows: [
            {id: "r1", title: "运行中研究", status: "running"},
            {id: "r2", title: "草稿研究", status: "draft"},
          ],
        }}
      />,
    );
    expect(screen.getByTestId("rail-status-label")).toHaveTextContent("等确认");
    const rows = screen.getAllByTestId("research-row");
    expect(within(rows[0]).getByTestId("list-status-pill")).toHaveTextContent("运行中");
    expect(within(rows[1]).getByTestId("list-status-pill")).toHaveTextContent("草稿");
    expect(screen.getByRole("link", {name: "打开确认卡"})).toBeInTheDocument();
  });

  it("renders confirm card pulse chrome", () => {
    const view: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      settings,
      symbolSelection: {
        count: 1,
        listName: "US-EQ",
        listVersion: "v3",
        symbols: ["600519.SH"],
        source: "user_override",
        dataStart: "2016-01-01",
        dataEnd: "2025-12-31",
        dataCutoff: "2025-12-31",
        dataSource: "AkShare 日线（新浪优先）",
      },
    };
    const unlockBrief = vi.fn(async () => undefined);
    render(<ConfirmRunCard api={{...api, unlockBrief}} view={view} />);
    expect(screen.getByTestId("confirm-run-card")).toHaveClass("tech-pulse-card");
    expect(screen.getByRole("heading", {name: "确认开跑"})).toBeInTheDocument();
    expect(screen.getByTestId("symbol-selection")).toHaveClass("confirm-data-panel");
    expect(screen.getByText("将使用的数据")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "开跑"})).toBeInTheDocument();
    expect(screen.getByTestId("confirm-return-draft")).toHaveTextContent("再修改");
    fireEvent.click(screen.getByTestId("confirm-return-draft"));
    expect(unlockBrief).toHaveBeenCalledWith("r-1");
  });

  it("renders running orbit and quota only with parseable effective string", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 2,
      effective: "3h12 / 12h",
      currentAction: "历史模拟",
      coverage: "覆盖仍在底线之上",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    const orbit = screen.getByTestId("version-orbit");
    expect(orbit).toHaveTextContent("v2");
    expect(orbit).toHaveTextContent("历史模拟");
    expect(screen.getByTestId("effective-quota-progress")).toBeInTheDocument();
  });

  it("renders quota bar from effective and remaining when slash form absent", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "0.00 小时",
      remaining: "12.00 小时",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("effective-quota-progress")).toBeInTheDocument();
    expect(screen.getByText("有效研究额度")).toBeInTheDocument();
  });

  it("hides quota progress when effective has no total (no fake meter)", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "3.00h",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    expect(screen.queryByTestId("effective-quota-progress")).not.toBeInTheDocument();
  });

  it("renders awaiting confirm pulse card", () => {
    const view: DesktopView = {
      kind: "awaiting_confirm",
      researchId: "r-1",
      version: 2,
      confirmKind: "economic",
      proposed: "改",
      reason: "因",
      effect: "果",
    };
    render(<AwaitingConfirmCard api={api} view={view} />);
    expect(screen.getByTestId("awaiting-confirm-card")).toHaveClass("tech-pulse-card");
  });

  it("keeps A-share ticker nowrap in thesis", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [],
      settings,
    };
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("brief-thesis-value").querySelector(".cn-ticker-nowrap")).toHaveTextContent(
      "600519.SH",
    );
  });

  it("keeps list row actions on one line and shows 未通过 for ended rows", () => {
    const longTitle = "A股股票 600519.SH 低波动量价回归 ".repeat(3);
    render(
      <App
        api={api}
        initialView={{
          kind: "research_list",
          rows: [
            {id: "r-fail", title: longTitle, status: "ended"},
            {id: "r-ok", title: "行业动量", status: "completed"},
          ],
        }}
      />,
    );
    const failedRow = screen.getAllByTestId("research-row")[0];
    expect(failedRow).toHaveClass("research-row--failed");
    expect(within(failedRow).getByTestId("list-status-pill")).toHaveTextContent("未通过");
    const actions = within(failedRow).getByText("进入").parentElement;
    expect(actions).toHaveClass("row-actions");
    expect(within(actions as HTMLElement).getByText("删除")).toBeInTheDocument();
    expect(within(actions as HTMLElement).getByText("未通过")).toBeInTheDocument();
  });

  it("tags failed completed atmosphere for red orb styling", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-fail",
      status: "completed",
      title: "高频试错",
      selectedRoundId: "r1",
      selectedMethodId: "m1",
      exportKind: "research_record_only",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: false,
      },
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-fail" />);
    expect(screen.getByTestId("tech-pulse-atmosphere")).toHaveAttribute("data-atmosphere-tone", "failed");
    expect(screen.getByTestId("night-shell").querySelector(".content.completed.tech-pulse-failed-tone")).toBeTruthy();
  });

  it("renders failed completed card with coral export primary", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-fail",
      status: "completed",
      title: "高频试错",
      selectedRoundId: "r1",
      selectedMethodId: "m1",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: false,
      },
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-fail" />);
    expect(screen.getByTestId("completed-failed-eyebrow")).toHaveTextContent("未通过门禁");
    expect(screen.getByTestId("export-research-record-primary")).toBeEnabled();
    expect(screen.getByTestId("export-strategy-pack-locked")).toBeDisabled();
    expect(screen.queryByTestId("export-research-record")).not.toBeInTheDocument();
    const tools = screen.getByTestId("completed-tools-details");
    expect((tools as HTMLDetailsElement).open).toBe(false);
  });

  it("renders thicker effective quota track", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "0.00 小时",
      remaining: "12.00 小时",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    const progress = screen.getByTestId("effective-quota-progress");
    expect(progress.querySelector(".effective-quota-track")).toBeTruthy();
    expect(progress.querySelector(".effective-quota-fill")).toBeTruthy();
  });

  it("renders completed export-ready chrome when eligible", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "低波动量价回归",
      selectedRoundId: "r1",
      selectedMethodId: "m1",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("completed-screen")).toBeInTheDocument();
    expect(screen.getByTestId("export-ready-eyebrow")).toBeInTheDocument();
  });

  it("applies run-start ritual on confirm → running without fake progress UI", async () => {
    mockMatchMedia(false);
    const confirmView: DesktopView = {
      kind: "confirm_run",
      researchId: "r-ritual",
      dialogue: [],
      settings,
    };
    const runningView: DesktopView = {
      kind: "running",
      researchId: "r-ritual",
      status: "running",
      version: 1,
      effective: "1h / 12h",
      coverage: "ok",
      rounds: [],
    };

    let current: DesktopView = confirmView;
    const ritualApi = minimalDesktopApi({
      fetchView: vi.fn(async () => current),
      confirmRun: vi.fn(async () => {
        current = runningView;
      }),
    });

    render(<App api={ritualApi} initialView={confirmView} initialRoute="#/research/r-ritual" />);
    fireEvent.click(screen.getByRole("button", {name: "开跑"}));
    await waitFor(() => expect(screen.getByTestId("running-screen")).toBeInTheDocument());
    await waitFor(() =>
      expect(document.querySelector('[data-run-start-ritual="active"]')).toBeTruthy(),
    );
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/X\/N/i)).not.toBeInTheDocument();
    await waitFor(
      () => expect(document.querySelector('[data-run-start-ritual="active"]')).toBeFalsy(),
      {timeout: RUN_START_RITUAL_MS + 300},
    );
  });

  it("does not show placeholder round labels on the version orbit", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 2,
      effective: "1h / 12h",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    const orbit = screen.getByTestId("version-orbit");
    expect(orbit.textContent).not.toMatch(/X\/N/i);
    expect(orbit).toHaveTextContent("v2");
  });
});
