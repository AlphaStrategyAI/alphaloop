import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView, SidecarUiState} from "./contracts";

afterEach(() => cleanup());

const listView: DesktopView = {kind: "research_list", rows: []};

const api: DesktopApi = {
  fetchView: vi.fn(async () => listView),
  createDraft: vi.fn(),
  confirmRun: vi.fn(),
  setResearchSymbol: vi.fn(async () => undefined),
  answerSymbolAsk: vi.fn(async () => undefined),
  useHintedSymbol: vi.fn(async () => undefined),
  revertSymbolAsk: vi.fn(async () => undefined),
  removeMarketSide: vi.fn(async () => undefined),
  dismissMismatchedSymbol: vi.fn(async () => undefined),
  chooseDefaultMarket: vi.fn(async () => undefined),
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

const stopped: SidecarUiState = {
  phase: "stopped",
  restartCount: 5,
  maxRestarts: 5,
  message: "引擎已停止：sqlite",
};

describe("sidecar supervision UI", () => {
  it("shows stopped banner and restart button", async () => {
    const restartSidecar = vi.fn(async () => undefined);
    render(
      <App
        api={api}
        initialView={listView}
        pollSidecar={async () => stopped}
        restartSidecar={restartSidecar}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("sidecar-stopped")).toHaveTextContent("引擎已停止");
    });
    fireEvent.click(screen.getByRole("button", {name: "重启引擎"}));
    expect(restartSidecar).toHaveBeenCalled();
  });

  it("shows a test-data badge only when the engine marks synthetic prices", () => {
    const {unmount} = render(<App api={api} initialView={{...listView, testData: true}} />);
    expect(screen.getByTestId("test-data-badge")).toHaveTextContent("测试数据");
    unmount();
    render(<App api={api} initialView={listView} />);
    expect(screen.queryByTestId("test-data-badge")).not.toBeInTheDocument();
  });
});
