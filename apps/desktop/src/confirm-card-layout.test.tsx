import {render, screen, within} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {ConfirmRunCard} from "./App";
import type {DesktopApi} from "./contracts";

describe("ConfirmRunCard settings grid", () => {
  it("keeps label, value and edit action on one row; pool name once", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
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
            universe_symbols: "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池",
            max_effective_hours: "4 小时",
            round1_methods: "分段稳健性检验",
            coverage_floor: "至少 25 个标的",
          },
        }}
      />,
    );
    const row = screen.getByTestId("brief-slot-universe");
    const edit = within(row).getByTestId("edit-slot-universe");
    expect(row.contains(edit)).toBe(true);
    const symbols = screen.getByTestId("universe-symbols");
    expect(symbols.textContent).toBe(
      "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池",
    );
    expect((symbols.textContent?.match(/美股大市值/g) ?? []).length).toBe(1);
  });

  it("shows the v2 pool name without a version, and keeps the version in the detail line", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    render(
      <ConfirmRunCard
        api={api}
        view={{
          kind: "confirm_run",
          researchId: "r-2",
          dialogue: [],
          chatEnabled: false,
          settings: {
            thesis: "均值回归",
            universe: "美股 · 股票",
            max_effective_hours: "4 小时",
            round1_methods: "分段稳健性检验",
            coverage_floor: "至少 25 个标的",
          },
          symbolSelection: {
            count: 503,
            listName: "美股大市值池 · 503 只 · 名单日 2026-10-16",
            listVersion: "2",
            summaryLine: "美股大市值池 · 503 只 · 名单日 2026-10-16",
            listNote: "取自标普 500 在名单日的成分，非时点成分",
            listNameEn: "US large-cap universe · 503 names · list date 2026-10-16",
            listNoteEn: "Taken from S&P 500 membership on the list date; not point-in-time.",
            generatedDate: "2026-10-16",
            symbols: ["AAPL"],
            source: "default_pool",
            dataStart: "2014-10-19",
            dataEnd: "2026-10-19",
            dataCutoff: "2026-10-19",
            dataSource: "雅虎日线",
            isDefaultPool: true,
          },
        }}
      />,
    );
    const summary = screen.getByTestId("symbol-selection-summary");
    expect(summary.textContent).toBe("美股大市值池 · 503 只 · 名单日 2026-10-16");
    expect(summary.textContent).not.toContain("版本");
    expect(summary.textContent).not.toContain("标普 500");
    expect(screen.getByTestId("symbol-selection-note").textContent).toBe(
      "取自标普 500 在名单日的成分，非时点成分",
    );
    expect(screen.getByTestId("symbol-selection-version").textContent).toBe("版本 2");
  });
});
