import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import dialogueCommandSource from "./dialogueCommands.ts?raw";
import type {DesktopView} from "./contracts";
import {commandForUtterance} from "./dialogueCommands";
import {I18nProvider} from "./i18n/I18nProvider";
import {runtimeUtteranceExamples} from "./i18n/runtimeCommandUtterances";
import {CompletedScreen} from "./screens/CompletedScreen";
import {RunningScreen} from "./screens/RunningScreen";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const running: DesktopView = {
  kind: "running",
  researchId: "r-run",
  status: "running",
  version: 1,
  effective: "1 小时",
  coverage: "覆盖",
  rounds: [],
};

const completed: DesktopView = {
  kind: "completed",
  researchId: "r-done",
  status: "completed",
  title: "研究",
  version: 1,
  effective: "1 小时",
  selectedRoundId: "round-1",
  selectedMethodId: "scorecard.market",
  eligibility: {
    allMethodsPassed: true,
    noPendingConfirm: true,
    reverifiesPassed: true,
    pitExecutedAndPassed: true,
    coverageSatisfied: false,
  },
  failedExportChecks: ["coverage_satisfied"],
  exportBlockerMessages: ["数据覆盖未达到冻结底线，暂不能导出策略包"],
  reverifyOptions: {
    rounds: [{roundId: "round-1", roundLabel: "第 1 轮", methods: [{methodId: "scorecard.market", methodLabel: "市场计分卡"}]}],
  },
};

describe("dialogue and buttons share commands", () => {
  it("maps Chinese and English phrases onto the button commands", () => {
    const examples = runtimeUtteranceExamples();
    expect(examples.length).toBeGreaterThan(0);
    for (const example of examples) {
      expect(commandForUtterance(example.text)).toEqual(example.command);
      expect(commandForUtterance(example.text.toUpperCase())).toEqual(example.command);
    }
    expect(dialogueCommandSource).not.toMatch(/[\u4e00-\u9fff]/);
    expect(commandForUtterance("现在在做什么")).toEqual({type: "send_dialogue", message: "现在在做什么"});
    expect(commandForUtterance("what are we doing")).toEqual({type: "send_dialogue", message: "what are we doing"});
  });

  it("runs pause from the button and from both languages", () => {
    const pauseResearch = vi.fn(async () => undefined);
    const sendDialogue = vi.fn(async () => undefined);
    const api = minimalDesktopApi({pauseResearch, sendDialogue});
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <RunningScreen api={api} view={running} modification="" onModificationChange={() => undefined} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button", {name: "暂停"}));
    const input = screen.getByTestId("runtime-dialogue-input");
    fireEvent.change(input, {target: {value: "pause"}});
    fireEvent.submit(screen.getByTestId("runtime-dialogue-form"));
    fireEvent.change(screen.getByTestId("runtime-dialogue-input"), {target: {value: "暂停"}});
    fireEvent.submit(screen.getByTestId("runtime-dialogue-form"));
    fireEvent.change(screen.getByTestId("runtime-dialogue-input"), {target: {value: "现在在做什么"}});
    fireEvent.submit(screen.getByTestId("runtime-dialogue-form"));
    expect(pauseResearch).toHaveBeenCalledTimes(3);
    expect(pauseResearch).toHaveBeenCalledWith("r-run");
    expect(sendDialogue).toHaveBeenCalledWith("r-run", "现在在做什么");
  });

  it("hides the strategy pack when coverage fails and exports a record from text or the button", async () => {
    const exportArtifact = vi.fn(async () => "/tmp/record.zip");
    const reverify = vi.fn(async () => undefined);
    const api = minimalDesktopApi({exportArtifact, reverify});
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <CompletedScreen api={api} view={completed} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("export-strategy-pack-locked")).toBeDisabled();
    expect(screen.getByTestId("export-blockers")).toHaveTextContent("数据覆盖未达到冻结底线");
    fireEvent.click(screen.getByTestId("export-research-record-primary"));
    fireEvent.change(screen.getByTestId("runtime-dialogue-input"), {target: {value: "export research record"}});
    fireEvent.submit(screen.getByTestId("runtime-dialogue-form"));
    fireEvent.change(screen.getByTestId("runtime-dialogue-input"), {target: {value: "reverify"}});
    fireEvent.submit(screen.getByTestId("runtime-dialogue-form"));
    expect(exportArtifact).toHaveBeenCalledTimes(2);
    expect(exportArtifact).toHaveBeenCalledWith("r-done", "research_record");
    expect(reverify).toHaveBeenCalledWith("r-done", "round-1", "scorecard.market");
  });
});
