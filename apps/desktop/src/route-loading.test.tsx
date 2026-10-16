import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const runningView: DesktopView = {
  kind: "running",
  researchId: "r-run",
  status: "running",
  version: 1,
  effective: "1.00h",
  coverage: "当前 1 个标的",
  rounds: [],
};

const listView: DesktopView = {kind: "research_list", rows: []};

function makeApi(fetchView: DesktopApi["fetchView"]): DesktopApi {
  return {
    fetchView,
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
}

describe("route loading", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("does not flash stale running screen while fetching a new route", async () => {
    let resolveList: (v: DesktopView) => void = () => undefined;
    const fetchView = vi.fn((route: string) => {
      if (route === "#/research") {
        return new Promise<DesktopView>((resolve) => {
          resolveList = resolve;
        });
      }
      return Promise.resolve(runningView);
    });
    render(
      <App
        api={makeApi(fetchView)}
        initialView={runningView}
        initialRoute="#/research/r-run"
      />,
    );
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "running");

    window.location.hash = "#/research";
    window.dispatchEvent(new HashChangeEvent("hashchange"));

    await waitFor(() => {
      expect(screen.getByTestId("route-loading")).toBeInTheDocument();
    });
    expect(screen.queryByText(/迭代与验证/)).not.toBeInTheDocument();

    resolveList(listView);
    await waitFor(() => {
      expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "research_list");
    });
    expect(screen.queryByTestId("route-loading")).not.toBeInTheDocument();
  });
});
