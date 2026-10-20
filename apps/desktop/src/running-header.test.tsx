import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import type {ReactElement} from "react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {I18nProvider} from "./i18n/I18nProvider";

const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};

function renderZh(ui: ReactElement) {
  return render(<I18nProvider initial={ZH}>{ui}</I18nProvider>);
}

afterEach(() => cleanup());

const api: DesktopApi = {
  fetchView: vi.fn(async () => runningView),
  createDraft: vi.fn(),
  confirmRun: vi.fn(),
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

const runningView: DesktopView = {
  kind: "running",
  researchId: "r-1",
  status: "running",
  version: 2,
  effective: "3.00h",
  coverage: "底线 OK",
  dataCutoff: "2026-10-17",
  rounds: [],
  currentAction: "idle",
};

describe("running header", () => {
  it("shows running in the rail while a US quote fetch is in progress", () => {
    const fetching: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      settings: {
        thesis: "t",
        universe: "u",
        max_effective_hours: "4 小时",
        round1_methods: "m",
        coverage_floor: "c",
      },
      hostStatus: "awaiting_confirm",
      marketDataProgress: {done: 12, total: 503, source: "yahoo"},
    };
    renderZh(
      <App
        api={{...api, fetchView: vi.fn(async () => fetching)}}
        initialView={fetching}
        initialRoute="#/research/r-1"
      />,
    );
    const rail = screen.getByTestId("host-status");
    expect(rail).toHaveClass("running");
    expect(rail).not.toHaveClass("awaiting_confirm");
    expect(screen.getByTestId("rail-status-label")).toHaveTextContent("运行中");
    expect(screen.getByTestId("market-data-progress")).toHaveTextContent("正在取行情 12/503");
  });

  it("shows market-data progress from the side channel while fetchView is stuck", async () => {
    const fetchView = vi.fn(() => new Promise<DesktopView>(() => undefined));
    const pollMarketDataProgress = vi.fn(async () => ({
      marketDataProgress: {done: 12, total: 503, source: "yahoo" as const},
      hostStatus: "running" as const,
    }));
    renderZh(
      <App
        api={{...api, fetchView, pollMarketDataProgress}}
        initialView={runningView}
        initialRoute="#/research/r-1"
      />,
    );
    expect(await screen.findByTestId("market-data-progress")).toHaveTextContent("正在取行情 12/503");
  });

  it("hides idle currentAction label in the running header", () => {
    renderZh(<App api={api} initialView={runningView} initialRoute="#/research/r-1" />);
    const panel = screen.getByTestId("running-screen");
    expect(panel.textContent).toContain("第 2 版");
    expect(panel.textContent).not.toContain("idle");
    expect(panel.textContent).toMatch(/数据截止：2026-10-17(?![\d:])/);
  });

  it("shows how many names the market-data load has finished", () => {
    renderZh(
      <App
        api={api}
        initialView={{...runningView, marketDataProgress: {done: 12, total: 503, source: "yahoo"}}}
        initialRoute="#/research/r-1"
      />,
    );
    expect(screen.getByTestId("market-data-progress").textContent).toBe("正在取行情 12/503");
  });
});
