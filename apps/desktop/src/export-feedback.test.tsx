import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const completedView: DesktopView = {
  kind: "completed",
  researchId: "r-export",
  status: "completed",
  title: "测试研究",
  selectedRoundId: "r-export-v1-r1",
  selectedMethodId: "overfit.walk",
  eligibility: {
    allMethodsPassed: true,
    noPendingConfirm: true,
    reverifiesPassed: true,
    pitExecutedAndPassed: true,
  },
};

function makeApi(exportArtifact: DesktopApi["exportArtifact"]): DesktopApi {
  return {
    fetchView: vi.fn(async () => completedView),
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
    exportArtifact,
    revealExportInFolder: vi.fn(),
    reverify: vi.fn(),
    reviseMethod: vi.fn(),
    createMethod: vi.fn(),
  };
}

describe("export feedback", () => {
  it("shows success path after research_record export", async () => {
    const path = "/home/user/alphaloop/exports/r-export-research-record.zip";
    const exportArtifact = vi.fn(async () => path);
    render(<App api={makeApi(exportArtifact)} initialView={completedView} />);
    fireEvent.click(screen.getByRole("button", {name: "导出研究记录包"}));
    await waitFor(() => {
      expect(screen.getByTestId("export-success")).toHaveTextContent(`已导出到 ${path}`);
    });
    expect(exportArtifact).toHaveBeenCalledWith("r-export", "research_record");
  });

  it("shows error when export fails", async () => {
    const exportArtifact = vi.fn(async () => {
      throw new Error("not eligible");
    });
    render(<App api={makeApi(exportArtifact)} initialView={completedView} />);
    fireEvent.click(screen.getByRole("button", {name: "导出研究记录包"}));
    await waitFor(() => {
      expect(screen.getByTestId("export-error")).toHaveTextContent("导出失败：not eligible");
    });
  });
});
