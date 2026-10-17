import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const api: DesktopApi = {
  fetchView: vi.fn(async () => runningView),
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

const runningView: DesktopView = {
  kind: "running",
  researchId: "r-1",
  status: "running",
  version: 2,
  effective: "3.00h",
  coverage: "底线 OK",
  rounds: [],
  currentAction: "idle",
};

describe("running header", () => {
  it("hides idle currentAction label in the running header", () => {
    render(<App api={api} initialView={runningView} initialRoute="#/research/r-1" />);
    const header = screen.getByText(/第 2 版/).closest("header");
    expect(header).toBeTruthy();
    expect(header?.textContent).not.toContain("idle");
  });
});
