import "@testing-library/jest-dom/vitest";
import {render, screen} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {ConfirmRunCard} from "./App";
import type {DesktopApi} from "./contracts";

describe("confirm data notice", () => {
  it("shows transient market data message on confirm card", () => {
    const api = {unlockBrief: vi.fn(), confirmRun: vi.fn()} as unknown as DesktopApi;
    render(
      <ConfirmRunCard
        api={api}
        view={{
          kind: "confirm_run",
          researchId: "r-1",
          dialogue: [],
          chatEnabled: false,
          confirmDataNotice: "行情数据源暂时不可用，请稍后重试",
          settings: {
            thesis: "测试",
            universe: "美股 · 股票",
            max_effective_hours: "3 小时",
            round1_methods: "分段稳健性检验",
            coverage_floor: "至少 25 个标的",
          },
        }}
      />,
    );
    expect(screen.getByTestId("confirm-data-notice")).toHaveTextContent(
      "行情数据源暂时不可用，请稍后重试",
    );
  });
});
