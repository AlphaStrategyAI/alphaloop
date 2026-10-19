import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App, ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const NOTICE = "策略族：均值回归（V1 唯一）· 论点文字仅作记录，不改变策略";

const confirmBase: DesktopView = {
  kind: "confirm_run",
  researchId: "r-1",
  dialogue: [],
  settings: {
    thesis: "美股动量策略",
    universe: "美股 · 股票",
    max_effective_hours: "4 小时",
    round1_methods: "样本外稳定",
    coverage_floor: "至少 25 个标的",
  },
};

describe("mean-reversion-only notice", () => {
  it("shows the confirm-card notice only when the engine sends one", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    const {rerender} = render(
      <ConfirmRunCard api={api} view={{...confirmBase, meanReversionOnlyNotice: NOTICE}} />,
    );
    expect(screen.getByTestId("mean-reversion-only-notice")).toHaveTextContent(NOTICE);
    rerender(
      <ConfirmRunCard
        api={api}
        view={{
          ...confirmBase,
          settings: {...confirmBase.settings, thesis: "美股股票的均值回归"},
        }}
      />,
    );
    expect(screen.queryByTestId("mean-reversion-only-notice")).not.toBeInTheDocument();
  });

  it("shows the completed-page notice only for a non-mean-reversion thesis", () => {
    const base: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "美股动量策略",
      selectedRoundId: "round-1",
      selectedMethodId: "overfit.walk",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      meanReversionOnlyNotice: NOTICE,
    };
    render(<App api={minimalDesktopApi()} initialView={base} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("mean-reversion-only-notice")).toHaveTextContent("不改变策略");
    cleanup();
    render(
      <App
        api={minimalDesktopApi()}
        initialView={{...base, title: "美股股票的均值回归", meanReversionOnlyNotice: null}}
        initialRoute="#/research/r-1"
      />,
    );
    expect(screen.queryByTestId("mean-reversion-only-notice")).not.toBeInTheDocument();
  });
});
