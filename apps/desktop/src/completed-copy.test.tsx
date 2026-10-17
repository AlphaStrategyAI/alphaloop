import "@testing-library/jest-dom/vitest";
import {cleanup, render} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

function makeApi(view: DesktopView): DesktopApi {
  return {
  fetchView: vi.fn(async () => view),
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

const eligibility = {
  allMethodsPassed: false,
  noPendingConfirm: true,
  reverifiesPassed: true,
  pitExecutedAndPassed: false,
};

const exhaustedSubtitle =
  "验证未通过且实现层迭代预算已用尽（1/1 轮）。本数据窗口累计 1 轮；轮数越多，偶然通过的可能性越高。未通过门禁：市场计分卡 (scorecard.market)。只能导出研究记录包。可点「继续迭代」追加预算后再跑（阈值不变）。";

describe("completed screen copy", () => {
  it.each([
    ["completed", "completed" as const],
    ["ended", "ended" as const],
  ])("shows exhausted budget copy once on %s status", (_label, status) => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status,
      title: "测试",
      subtitle: exhaustedSubtitle,
      honestStopHint: null,
      selectedRoundId: "r-1",
      selectedMethodId: "m-1",
      eligibility,
    };
    const {container} = render(<App api={makeApi(view)} initialView={view} />);
    const text = container.textContent ?? "";
    expect(text.match(/预算已用尽/g)?.length).toBe(1);
  });
});
