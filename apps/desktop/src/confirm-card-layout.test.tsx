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
            universe_symbols: "40 只 · 美股大市值（版本 1）",
            max_effective_hours: "4 小时",
            round1_methods: "走样检验",
            coverage_floor: "至少 25 个标的",
          },
        }}
      />,
    );
    const row = screen.getByTestId("brief-slot-universe");
    const edit = within(row).getByTestId("edit-slot-universe");
    expect(row.contains(edit)).toBe(true);
    const symbols = screen.getByTestId("universe-symbols");
    expect(symbols.textContent).toBe("40 只 · 美股大市值（版本 1）");
    expect((symbols.textContent?.match(/美股大市值/g) ?? []).length).toBe(1);
  });
});
