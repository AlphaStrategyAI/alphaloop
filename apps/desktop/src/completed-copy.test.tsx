import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

function makeApi(view: DesktopView): DesktopApi {
  return {
  fetchView: vi.fn(async () => view),
  createDraft: vi.fn(),
  confirmRun: vi.fn(),
  setResearchSymbol: vi.fn(async () => undefined),
  answerSymbolAsk: vi.fn(async () => undefined),
  useHintedSymbol: vi.fn(async () => undefined),
  revertSymbolAsk: vi.fn(async () => undefined),
  removeMarketSide: vi.fn(async () => undefined),
  dismissMismatchedSymbol: vi.fn(async () => undefined),
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

const eligibility = {
  allMethodsPassed: false,
  noPendingConfirm: true,
  reverifiesPassed: true,
  pitExecutedAndPassed: false,
};

const exhaustedSubtitle =
  "本窗口所有研究累计 1 轮；轮数越多，偶然通过的可能性越高。未通过门禁：市场计分卡。只能导出研究记录包。可点「继续迭代」追加预算后再跑（阈值不变）。";

describe("completed screen copy", () => {
  it.each([
    ["completed", "completed" as const],
    ["ended", "ended" as const],
  ])("shows exhausted budget copy once on %s status", (_label, status) => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status,
      title: "测试",
      subtitle: exhaustedSubtitle,
      honestStopHint:
        "实现层迭代预算已用尽（1/1 轮）。验证仍未通过；只能导出研究记录包。",
      selectedRoundId: "r-1",
      selectedMethodId: "m-1",
      eligibility,
    };
    const {container} = render(<App api={makeApi(view)} initialView={view} />);
    const text = container.textContent ?? "";
    expect(text.match(/预算已用尽/g)?.length).toBe(1);
  });

  it("shows this research's window cumulative next to the all-research total", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "测试",
      selectedRoundId: "r-1",
      selectedMethodId: "m-1",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      researchCumulativeLabel: "本研究在本窗口累计 5 轮",
      workbenchHeaderSummary: "本窗口所有研究累计 5 轮",
      windowCumulativeLabel: "本窗口所有研究累计 5 轮",
    };
    const {container} = render(<App api={makeApi(view)} initialView={view} />);
    const header = container.querySelector("[data-testid=completed-workbench-header]");
    expect(header?.textContent).toContain("本研究在本窗口累计 5 轮");
    expect(header?.textContent).toContain("本窗口所有研究累计 5 轮");
    expect(header?.textContent).not.toContain("本研究在本窗口累计 0 轮");
    expect(header?.textContent?.match(/本窗口所有研究累计 5 轮/g)?.length).toBe(1);
  });

  it("shows pit scope, cited count, and the no-external-evidence note", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-pit",
      status: "completed",
      title: "测试",
      selectedRoundId: "r-1",
      selectedMethodId: "m-1",
      eligibility: {...eligibility, pitExecutedAndPassed: true},
      pitDetail: {
        executed: true,
        passed: true,
        revision: "pit-v2",
        evidenceUsed: 0,
        undatedExcluded: ["local:note.md"],
        scope: "只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订",
        note: "未引用外部资料",
      },
    };
    render(<App api={makeApi(view)} initialView={view} />);
    const detail = document.querySelector("[data-testid='pit-detail']");
    expect(detail?.textContent).toContain("未引用外部资料");
    expect(detail?.textContent).toContain("已采信 0 份");
    expect(detail?.textContent).toContain("已浏览未采信 1 份");
    expect(detail?.textContent).toContain("不覆盖标的池/复权/财务修订");
  });

  it("shows the first late paper, year-end rule, and separates the two cutoffs", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-pit-fail",
      status: "ended",
      title: "均值回归",
      selectedRoundId: "r-1",
      selectedMethodId: "m-1",
      eligibility: {...eligibility, pitExecutedAndPassed: false},
      exportBlockerMessages: ["时点一致性未通过，暂不能导出策略包"],
      backtestCutoff: "2026-10-16",
      symbolSelection: {
        count: 40,
        listName: "美股大市值",
        listVersion: "1",
        symbols: ["AAPL"],
        source: "default_pool",
        dataStart: "2014-10-19",
        dataEnd: "2026-10-19",
        dataCutoff: "2026-10-19",
        dataSource: "雅虎日线",
      },
      pitDetail: {
        executed: true,
        passed: false,
        revision: "pit-v2",
        evidenceUsed: 5,
        undatedExcluded: [],
        scope: "只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订",
        note: "",
        backtestCutoff: "2026-10-16",
        violationCount: 1,
        firstViolation: {
          materialId: "doi:10.37155/3041-0827-0207-3",
          title: "年份论文",
          publishedAt: "2026-12-31",
          precision: "year",
          reason: "after_cutoff",
        },
      },
    };
    render(<App api={makeApi(view)} initialView={view} />);
    const reason = document.querySelector("[data-testid='pit-failure-reason']");
    expect(reason?.textContent).toContain("时点一致性未通过");
    expect(reason?.textContent).not.toContain("未通过或未执行");
    expect(reason?.textContent).toContain("年份论文");
    expect(reason?.textContent).toContain("DOI 10.37155/3041-0827-0207-3");
    expect(reason?.textContent).toContain("2026-12-31");
    expect(reason?.textContent).toContain("仅知年份，按年末计");
    expect(reason?.textContent).toContain("回测截止日 2026-10-16");
    expect(reason?.textContent).toMatch(/发布日 2026-12-31（仅知年份，按年末计），回测截止日 2026-10-16/);
    expect(reason?.textContent).toContain("共 1 条违规");
    const windowLine = document.querySelector("[data-testid='completed-symbol-selection']");
    expect(windowLine?.textContent).toContain("数据窗口截止 2026-10-19");
    expect(windowLine?.textContent).toContain("回测截止（最后交易日）2026-10-16");
    expect(windowLine?.textContent).toMatch(
      /数据区间 2014-10-19 至 2026-10-19（数据窗口截止 2026-10-19 · 回测截止（最后交易日）2026-10-16）/,
    );
    expect(screen.getByTestId("completed-gate-pills").textContent).toContain("时点一致性未通过");
    expect(screen.getByTestId("completed-gate-pills").textContent).not.toContain("未执行");
  });

  it("says the gate was not executed when PIT never ran", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-no-pit",
      status: "ended",
      title: "均值回归",
      selectedRoundId: "r-1",
      selectedMethodId: "m-1",
      eligibility: {...eligibility, pitExecutedAndPassed: false},
      pitDetail: {executed: false, passed: false},
    };
    render(<App api={makeApi(view)} initialView={view} />);
    expect(screen.getByTestId("completed-gate-pills").textContent).toContain("时点一致性未执行");
    expect(screen.getByTestId("completed-gate-pills").textContent).not.toContain("未通过或未执行");
    expect(document.querySelector("[data-testid='pit-failure-reason']")?.textContent).toContain(
      "时点一致性未执行，暂不能导出策略包",
    );
  });
});
