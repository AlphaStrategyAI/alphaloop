import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi({});

const list: DesktopView = {
  kind: "research_list",
  awaiting: {id: "r-wait", title: "等确认的研究", status: "awaiting_confirm"},
  rows: [
    {id: "r-confirm", title: "确认开跑的研究", status: "confirm_run"},
    {id: "r-run", title: "运行中的研究", status: "running"},
    {id: "r-pause", title: "暂停的研究", status: "paused"},
    {id: "r-done", title: "完成的研究", status: "completed"},
    {id: "r-fail", title: "未通过的研究", status: "ended"},
    {id: "r-draft", title: "草稿研究", status: "draft"},
  ],
};

describe("research list filters", () => {
  it("defaults to All and filters by the existing status", () => {
    render(<App api={api} initialView={list} initialRoute="#/research" />);
    expect(screen.getByTestId("research-list-filter-all")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("research-list-filters")).toHaveTextContent("全部");
    expect(screen.getByTestId("research-list-filters")).toHaveTextContent("待确认");
    expect(screen.getAllByTestId("research-row")).toHaveLength(5);
    expect(screen.getByTestId("awaiting-pinned-card")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-pinned-card")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("research-list-filter-paused"));
    expect(screen.getAllByTestId("research-row")).toHaveLength(1);
    expect(screen.getByText("暂停的研究")).toBeInTheDocument();
    expect(screen.queryByTestId("awaiting-pinned-card")).not.toBeInTheDocument();
    expect(screen.queryByText("还没有研究")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("research-list-filter-pending"));
    expect(screen.queryByTestId("research-row")).not.toBeInTheDocument();
    expect(screen.getByTestId("awaiting-pinned-card")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-pinned-card")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("research-list-filter-done"));
    const done = screen.getAllByTestId("research-row");
    expect(done).toHaveLength(2);
    expect(screen.getByText("完成的研究")).toBeInTheDocument();
    expect(screen.getByText("未通过的研究")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("research-list-filter-draft"));
    expect(screen.getAllByTestId("research-row")).toHaveLength(1);
    expect(screen.getByText("草稿研究")).toBeInTheDocument();
  });

  it("uses the English chip labels", () => {
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <App api={api} initialView={list} initialRoute="#/research" />
      </I18nProvider>,
    );
    const filters = screen.getByTestId("research-list-filters");
    expect(filters).toHaveTextContent("All");
    expect(filters).toHaveTextContent("Pending");
    expect(filters).toHaveTextContent("Running");
    expect(filters).toHaveTextContent("Paused");
    expect(filters).toHaveTextContent("Done");
    expect(filters).toHaveTextContent("Draft");
  });
});

describe("completed display hierarchy", () => {
  it("uses one gate Display and title-tier ink metrics when a gate failed", () => {
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
      metrics: {excessAnn: -0.073, maxDrawdown: -0.306},
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    const headings = screen.getAllByRole("heading", {level: 1});
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent("已完成 · 未通过门禁");
    expect(headings[0].textContent).not.toBe("已完成");
    expect(screen.queryByText("已完成", {selector: "h1"})).not.toBeInTheDocument();
    const metrics = screen.getByTestId("completed-metrics");
    expect(metrics).toHaveAttribute("data-metrics-tier", "title");
    expect(metrics).toHaveAttribute("data-metric-color", "ink");
    const card = screen.getByTestId("completed-focus-card");
    expect(card.compareDocumentPosition(metrics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("paused actions under the status head", () => {
  it("shows continue, change duration, and new version before the round list", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "paused",
      version: 2,
      effective: "12秒",
      coverage: "11.6 年",
      currentAction: "查资料",
      rounds: [
        {
          roundId: "round-1",
          number: 1,
          logicStatement: {statement: "均值回归", changedFromPrior: false, baselineVersion: 1},
          implementationDelta: {researchMethodChanges: [], modelChanges: [], paramChanges: []},
          trialCounters: {candidatesEvaluated: 1, candidatesPassed: 0, conclusionAttemptNumber: 1},
          verificationPassed: false,
        },
      ],
      lastError: {
        code: "DATA_SYMBOLS_EMPTY",
        message: "未选择任何标的，无法加载行情。请在确认开跑前锁定具体代码。",
        count: 1,
      },
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    const actions = screen.getByTestId("paused-actions");
    const rounds = screen.getByRole("heading", {name: "迭代与验证"});
    expect(actions.compareDocumentPosition(rounds) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(actions).toContainElement(screen.getByTestId("paused-resume"));
    expect(actions).toContainElement(screen.getByRole("button", {name: "改时长"}));
    expect(actions).toContainElement(screen.getByRole("button", {name: "开新版…"}));
    expect(actions).toContainElement(screen.getByTestId("go-set-tickers"));
    expect(screen.getByTestId("paused-resume")).toHaveTextContent("按当前版本继续");
    const roundCard = screen.getByTestId("round-card");
    expect(roundCard.compareDocumentPosition(screen.getByTestId("paused-resume")) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(0);
  });
});

describe("rail lockup", () => {
  it("selects research with a bar affordance and shortens the methods label", () => {
    render(<App api={api} initialView={{kind: "research_list", rows: []}} initialRoute="#/research" />);
    expect(screen.getByRole("link", {name: "研究"})).toHaveAttribute("data-selected-affordance", "bar");
    expect(screen.getByRole("link", {name: "方法"})).not.toHaveAttribute("data-selected-affordance");
    expect(screen.getByTestId("secret-vault-open")).not.toHaveClass("active");
    expect(screen.getByTestId("secret-vault-open")).toHaveTextContent("密钥");
  });

  it("keeps confirm status as a dot plus the existing phrase, not a new two-character label", () => {
    render(<App api={api} initialView={list} initialRoute="#/research" />);
    const label = screen.getByTestId("rail-status-label");
    const hidden = label.querySelector(".rail-status-sr");
    expect(hidden).toHaveTextContent("等确认");
    expect(Array.from(label.childNodes).some((node) => (
      node.nodeType === Node.TEXT_NODE && (node.textContent ?? "").includes("等确认")
    ))).toBe(false);
  });

  it("names the rail Keys in English", () => {
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <App api={api} initialView={{kind: "research_list", rows: []}} initialRoute="#/research" />
      </I18nProvider>,
    );
    expect(screen.getByTestId("secret-vault-open")).toHaveTextContent("Keys");
    expect(screen.getByRole("link", {name: "Methods"})).toBeInTheDocument();
  });
});
