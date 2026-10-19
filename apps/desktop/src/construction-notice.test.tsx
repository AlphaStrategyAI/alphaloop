import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App, ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const US_LINE = "单票 ≤5%、成本 5 bp（保守产品假设）";
const CN_LINE = "未模拟 T+1 与涨跌停，实际成交可能更差";

describe("A2 construction notices", () => {
  it("shows the confirm-card cost assumption when the engine sends one", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    const view: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      constructionNotice: US_LINE,
      settings: {
        thesis: "美股股票的均值回归",
        universe: "美股 · 股票",
        max_effective_hours: "4 小时",
        round1_methods: "样本外稳定",
        coverage_floor: "至少 25 个标的",
      },
    };
    render(<ConfirmRunCard api={api} view={view} />);
    expect(screen.getByTestId("construction-notice")).toHaveTextContent(US_LINE);
  });

  it("shows the A-share execution notice on the conclusion page", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "A股均值回归",
      selectedRoundId: "round-1",
      selectedMethodId: "overfit.walk",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      cnExecutionNotice: CN_LINE,
    };
    render(<App api={minimalDesktopApi()} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("cn-execution-notice")).toHaveTextContent(CN_LINE);
  });
});
