import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const view: DesktopView = {
  kind: "running",
  researchId: "r-1",
  status: "running",
  version: 2,
  effective: "0.10 小时",
  remaining: "2.90 小时",
  coverage: "底线 OK",
  rounds: [],
  versionOpenedNotice: "已开始第 2 版。",
};

const api: DesktopApi = {
  fetchView: vi.fn(async () => view),
  createDraft: vi.fn(),
  confirmRun: vi.fn(),
  setResearchSymbol: vi.fn(async () => undefined),
  answerSymbolAsk: vi.fn(async () => undefined),
  useHintedSymbol: vi.fn(async () => undefined),
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

describe("version opened banner", () => {
  it("shows modification confirm notice at top of running screen", () => {
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("version-opened-banner")).toHaveTextContent(
      "已开始第 2 版。",
    );
  });
});
