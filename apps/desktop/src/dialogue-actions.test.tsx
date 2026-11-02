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
import {AwaitingConfirmCard} from "./screens/AwaitingConfirmScreen";
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

  it("shows the English brief on the conclusion page", () => {
    const cjk = /[\u3400-\u9fff]/;
    render(
      <I18nProvider initial={{preference: "en", systemLocale: "en-US", resolved: "en"}}>
        <CompletedScreen
          api={minimalDesktopApi()}
          view={{
            ...completed,
            recentDialogue: [
              {role: "user", text: "美股股票 AAPL 的均值回归"},
              {role: "user", text: "4 小时"},
              {role: "user", text: "走样检验、样本外稳定"},
              {role: "user", text: "至少 1 个标的、10 年、缺失不超过 5%"},
              {role: "assistant", text: "五项研究设定已齐全，请检查确认开跑卡。"},
            ],
          }}
        />
      </I18nProvider>,
    );
    const log = screen.getByTestId("runtime-dialogue-log");
    expect(log).not.toHaveTextContent("美股股票 AAPL 的均值回归");
    expect(log).toHaveTextContent("4 h");
    expect(log).toHaveTextContent("Subperiod robustness check, Out-of-sample stability");
    expect(log).toHaveTextContent("At least 1 name, 10 years of data, missing no more than 5%");
    expect(log).toHaveTextContent("All five study settings are filled in. Review the confirmation card.");
    expect(log.textContent).not.toMatch(cjk);
  });

  it("paints the assistant reply on the completed screen", () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <CompletedScreen
          api={minimalDesktopApi()}
          view={{
            ...completed,
            recentDialogue: [
              {role: "user", text: "已经试过多少个"},
              {role: "assistant", text: "已提交 5 轮。"},
            ],
          }}
        />
      </I18nProvider>,
    );
    expect(screen.getByTestId("runtime-dialogue-log")).toHaveTextContent("已提交 5 轮");
  });

  it("opens a settings confirm card with reject and does not use the economic title", () => {
    const resolveConfirm = vi.fn(async () => undefined);
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <AwaitingConfirmCard
          api={minimalDesktopApi({resolveConfirm})}
          view={{
            kind: "awaiting_confirm",
            researchId: "r-hours",
            version: 1,
            confirmKind: "settings",
            proposed: "改前：max_effective_hours=0.5 改后：max_effective_hours=6",
            reason: "这项修改要确认后才会写入。",
            effect: "可拒绝并保持原设定。",
            whyChange: [],
            requestId: "settings-r-hours-v1",
          }}
        />
      </I18nProvider>,
    );
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("确认这项修改");
    expect(screen.getByText(/改前：/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: "不同意，维持原逻辑继续"}));
    expect(resolveConfirm).toHaveBeenCalledWith(
      "r-hours",
      "reject_keep_logic",
      undefined,
      "settings-r-hours-v1",
    );
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
