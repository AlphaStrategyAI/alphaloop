import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const api: DesktopApi = {
  fetchView: vi.fn(async () => ({kind: "research_list", rows: []})),
  createDraft: vi.fn(async () => "r"),
  confirmRun: vi.fn(async () => undefined),
  unlockBrief: vi.fn(async () => undefined),
  sendDialogue: vi.fn(async () => undefined),
  pauseResearch: vi.fn(async () => undefined),
  resumeResearch: vi.fn(async () => undefined),
  confirmModification: vi.fn(async () => undefined),
  continueIterate: vi.fn(async () => undefined),
  extendResearch: vi.fn(async () => undefined),
  deleteResearch: vi.fn(async () => undefined),
  resolveConfirm: vi.fn(async () => undefined),
  exportArtifact: vi.fn(async () => "/tmp/export.zip"),
  revealExportInFolder: vi.fn(async () => undefined),
  reverify: vi.fn(async () => undefined),
  reviseMethod: vi.fn(async () => undefined),
  createMethod: vi.fn(async () => undefined),
};

describe("lastError", () => {
  it("renders on paused running view", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "paused",
      version: 1,
      effective: "1h",
      coverage: "至少 1 个标的、5 年数据，缺失不超过 20%",
      rounds: [],
      lastError: {message: "UNIQUE constraint failed", count: 3},
    };
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("last-run-error")).toHaveTextContent("UNIQUE constraint failed");
    expect(screen.getByTestId("last-run-error")).toHaveTextContent("3 次");
  });
});
