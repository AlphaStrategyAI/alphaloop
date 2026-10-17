import {fireEvent, render, screen, waitFor} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {ConfirmRunScreen} from "./App";
import type {DesktopApi} from "./contracts";

describe("unlock slot dialogue", () => {
  it("posts slot question after 改一改 and keeps input visible", async () => {
    const unlockBrief = vi.fn(async () => undefined);
    const api = {
      unlockBrief,
      confirmRun: vi.fn(),
      sendDialogue: vi.fn(),
    } as unknown as DesktopApi;
    const {rerender} = render(
      <ConfirmRunScreen
        api={api}
        view={{
          kind: "confirm_run",
          researchId: "r-1",
          dialogue: [],
          chatEnabled: true,
          settings: {
            thesis: "t",
            universe: "u",
            max_effective_hours: "4 小时",
            round1_methods: "m",
            coverage_floor: "c",
          },
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("edit-slot-max_effective_hours"));
    expect(unlockBrief).toHaveBeenCalledWith("r-1", "max_effective_hours");
    rerender(
      <ConfirmRunScreen
        api={api}
        view={{
          kind: "confirm_run",
          researchId: "r-1",
          chatEnabled: true,
          dialogue: [
            {
              role: "assistant",
              text: "最多允许多少有效研究时间？例如：12 小时，或 30 分钟。暂停和等待确认不计时。",
            },
          ],
          settings: {
            thesis: "t",
            universe: "u",
            max_effective_hours: "",
            round1_methods: "m",
            coverage_floor: "c",
          },
        }}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/最多允许多少有效研究时间/)).toBeTruthy();
    });
    expect(screen.getByTestId("dialogue-input")).toBeTruthy();
  });
});
