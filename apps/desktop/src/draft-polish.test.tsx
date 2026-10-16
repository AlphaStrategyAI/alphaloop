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

const settings = {
  thesis: "",
  universe: "",
  max_effective_hours: "",
  round1_methods: "",
  coverage_floor: "",
};

describe("draft polish", () => {
  it("renders system intro before dialogue turns", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [
        {role: "user", text: "你好"},
        {role: "assistant", text: "回复"},
      ],
      settings,
    };
    render(<App api={api} initialView={view} />);
    const intro = screen.getByTestId("dialogue-system-intro");
    const turns = screen.getAllByTestId("dialogue-turn");
    expect(intro.compareDocumentPosition(turns[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("你好").className).toContain("user");
    expect(screen.getByText("回复").className).toContain("assistant");
  });

  it("does not show stray trailing slot label in dialogue bubbles", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [{role: "assistant", text: "美股低波动回归"}],
      settings,
    };
    render(<App api={api} initialView={view} />);
    expect(screen.queryByText(/，大致原理/)).not.toBeInTheDocument();
  });
});
