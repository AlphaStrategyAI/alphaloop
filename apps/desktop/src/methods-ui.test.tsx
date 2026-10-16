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

describe("method library UI", () => {
  it("marks the selected method link active, not always the first", () => {
    const view: DesktopView = {
      kind: "methods",
      selected: "second.method",
      methods: [
        {id: "scorecard.market", name: "市场计分卡", revision: "a".repeat(64), description: "d1"},
        {id: "second.method", name: "第二项", revision: "b".repeat(64), description: "d2"},
      ],
    };
    render(<App api={api} initialView={view} initialRoute="#/methods/second.method" />);
    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.includes("/methods/"));
    const active = links.find((a) => a.classList.contains("active"));
    expect(active?.textContent).toContain("第二项");
    expect(links[0].classList.contains("active")).toBe(false);
    const revision = screen.getAllByTitle("b".repeat(64))[0];
    expect(revision).toHaveTextContent(`${"b".repeat(8)}…`);
  });
});
