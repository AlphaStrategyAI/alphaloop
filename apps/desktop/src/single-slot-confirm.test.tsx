import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {ConfirmRunScreen} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const settings = {
  thesis: "低波动",
  universe: "美股 · 股票",
  max_effective_hours: "8 小时",
  round1_methods: "走样检验",
  coverage_floor: "至少 25 个标的",
};

describe("single-slot 改一改 on confirm card", () => {
  it("unlocks only the chosen slot and stays on confirm card UI", () => {
    const unlockBrief = vi.fn(async () => undefined);
    const api = {unlockBrief} as unknown as DesktopApi;
    const view: Extract<DesktopView, {kind: "confirm_run"}> = {
      kind: "confirm_run",
      researchId: "r-slot",
      dialogue: [],
      settings,
      symbolSelection: {
        count: 30,
        listName: "美股大盘",
        listVersion: "us_equity_large_cap_v1",
        symbols: ["SPY"],
        source: "default_pool",
        dataStart: "2016-01-01",
        dataEnd: "2026-10-17",
        dataCutoff: "2026-10-17",
        dataSource: "yahoo_daily",
        droppedForMissingData: 0,
        shrinkNote: null,
      },
    };
    render(<ConfirmRunScreen api={api} view={view} />);
    expect(screen.getByTestId("symbol-selection-summary")).toHaveTextContent("美股大盘");
    expect(screen.queryByTestId("pool-shrink-note")).toBeNull();
    fireEvent.click(screen.getByTestId("edit-slot-max_effective_hours"));
    expect(unlockBrief).toHaveBeenCalledWith("r-slot", "max_effective_hours");
    expect(screen.getByTestId("confirm-run-card")).toBeInTheDocument();
  });
});
