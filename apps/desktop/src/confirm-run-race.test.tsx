import "@testing-library/jest-dom/vitest";
import {act, cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const settings = {
  thesis: "均值回归",
  universe: "美股 · 股票",
  max_effective_hours: "4 小时",
  round1_methods: "走样检验",
  coverage_floor: "至少 25 个标的",
};

const confirmView: DesktopView = {
  kind: "confirm_run",
  researchId: "r-confirm",
  dialogue: [],
  settings,
};

const listView: DesktopView = {kind: "research_list", rows: []};

function makeApi(overrides: Partial<DesktopApi>): DesktopApi {
  return {
    fetchView: vi.fn(async () => confirmView),
    createDraft: vi.fn(),
    confirmRun: vi.fn(async () => undefined),
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
    ...overrides,
  };
}

describe("confirm run race", () => {
  beforeEach(() => {
    window.location.hash = "#/research/r-confirm";
  });

  it("drops a stale refresh after the route generation changes", async () => {
    const pending: Array<(view: DesktopView) => void> = [];
    const fetchView = vi.fn((route: string) => {
      if (route === "#/research/r-confirm") {
        return new Promise<DesktopView>((resolve) => {
          pending.push(resolve);
        });
      }
      return Promise.resolve(listView);
    });
    const api = makeApi({fetchView, confirmRun: vi.fn(async () => undefined)});
    render(
      <App api={api} initialView={confirmView} initialRoute="#/research/r-confirm" />,
    );

    fireEvent.click(screen.getByTestId("confirm-run-start"));
    await waitFor(() => expect(api.confirmRun).toHaveBeenCalledWith("r-confirm"));

    window.location.hash = "#/research";
    window.dispatchEvent(new HashChangeEvent("hashchange"));

    await waitFor(() => {
      expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "research_list");
    });
    expect(screen.queryByRole("heading", {name: "确认开跑"})).not.toBeInTheDocument();

    await act(async () => {
      for (const resolve of pending) resolve(confirmView);
      await Promise.resolve();
    });

    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "research_list");
    expect(screen.queryByRole("heading", {name: "确认开跑"})).not.toBeInTheDocument();
    expect(screen.queryByTestId("route-loading")).not.toBeInTheDocument();
  });

  it("disables 开跑 and shows in-progress copy until confirmRun settles", async () => {
    let resolveConfirm: () => void = () => undefined;
    const confirmRun = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveConfirm = resolve;
        }),
    );
    const fetchView = vi.fn(async () => confirmView);
    render(
      <App
        api={makeApi({confirmRun, fetchView})}
        initialView={confirmView}
        initialRoute="#/research/r-confirm"
      />,
    );

    const button = screen.getByTestId("confirm-run-start");
    expect(button).toHaveTextContent("开跑");
    expect(button).toBeEnabled();

    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveTextContent("开跑中…");
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(confirmRun).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();

    await act(async () => {
      resolveConfirm();
    });
    await waitFor(() => expect(button).toBeEnabled());
    expect(button).toHaveTextContent("开跑");
    expect(button).toHaveAttribute("aria-busy", "false");
  });

  it("re-enables 开跑 after confirmRun fails", async () => {
    const confirmRun = vi.fn(async () => {
      throw new Error("服务器内部错误，请稍后重试。");
    });
    render(
      <App
        api={makeApi({confirmRun, fetchView: vi.fn(async () => confirmView)})}
        initialView={confirmView}
        initialRoute="#/research/r-confirm"
      />,
    );

    fireEvent.click(screen.getByTestId("confirm-run-start"));
    const button = screen.getByTestId("confirm-run-start");
    await waitFor(() => expect(button).toBeEnabled());
    expect(button).toHaveTextContent("开跑");
    expect(screen.getByTestId("mutation-error")).toHaveTextContent("服务器内部错误，请稍后重试。");
  });
});
