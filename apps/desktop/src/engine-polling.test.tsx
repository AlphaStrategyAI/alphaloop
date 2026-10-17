import "@testing-library/jest-dom/vitest";
import {act, cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopView, SidecarUiState} from "./contracts";
import {emptyResearchListView, minimalDesktopApi} from "./test-fixtures";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const stopped: SidecarUiState = {
  phase: "stopped",
  restartCount: 5,
  maxRestarts: 5,
  message: "引擎已停止",
};

const running: SidecarUiState = {
  phase: "running",
  restartCount: 0,
  maxRestarts: 5,
  message: "",
};

describe("engine view polling when sidecar stopped", () => {
  it("does not poll fetchView on an interval while the engine is stopped", async () => {
    const fetchView = vi.fn(async () => emptyResearchListView);
    const api = minimalDesktopApi({fetchView});
    render(
      <App
        api={api}
        initialView={emptyResearchListView}
        pollSidecar={async () => stopped}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("sidecar-stopped")).toBeInTheDocument();
    });
    const callsAfterStop = fetchView.mock.calls.length;
    vi.useFakeTimers();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_500);
    });
    expect(fetchView.mock.calls.length).toBe(callsAfterStop);
  });

  it("resumes fetchView polling after a successful restart", async () => {
    let phase: SidecarUiState["phase"] = "stopped";
    const pollSidecar = vi.fn(async (): Promise<SidecarUiState> =>
      phase === "stopped" ? stopped : running,
    );
    const restartSidecar = vi.fn(async () => {
      phase = "running";
    });
    const fetchView = vi.fn(async () => emptyResearchListView);
    const api = minimalDesktopApi({fetchView});
    render(
      <App
        api={api}
        initialView={emptyResearchListView}
        pollSidecar={pollSidecar}
        restartSidecar={restartSidecar}
      />,
    );
    await waitFor(() => screen.getByTestId("sidecar-stopped"));
    const callsWhileStopped = fetchView.mock.calls.length;
    fireEvent.click(screen.getByRole("button", {name: "重启引擎"}));
    await waitFor(() => expect(restartSidecar).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByTestId("sidecar-stopped")).not.toBeInTheDocument());
    vi.useFakeTimers();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_100);
    });
    expect(fetchView.mock.calls.length).toBeGreaterThan(callsWhileStopped);
  });

  it("rejected fetchView polls do not surface as unhandled rejections", async () => {
    const unhandled: unknown[] = [];
    const onRejection = (event: PromiseRejectionEvent) => {
      unhandled.push(event.reason);
    };
    window.addEventListener("unhandledrejection", onRejection);
    const fetchView = vi.fn(async (): Promise<DesktopView> => {
      throw new Error("error sending request for url …/commands");
    });
    const api = minimalDesktopApi({fetchView});
    render(<App api={api} initialView={emptyResearchListView} pollSidecar={async () => running} />);
    vi.useFakeTimers();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    expect(fetchView.mock.calls.length).toBeGreaterThan(0);
    expect(unhandled).toHaveLength(0);
    window.removeEventListener("unhandledrejection", onRejection);
  });
});
