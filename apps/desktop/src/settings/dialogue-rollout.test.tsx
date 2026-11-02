import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import {I18nProvider} from "../i18n/I18nProvider";
import {EvidenceGradeNote} from "../screens/EvidenceGradeNote";
import {DialogueRolloutCard} from "./DialogueRolloutCard";
import {createMemoryDialogueRolloutPort} from "./dialogueRolloutPort";
import {SettingsPage} from "./SettingsPage";

afterEach(() => cleanup());

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};

describe("dialogue rollout settings", () => {
  it("ships off in both languages and records an explicit enable", async () => {
    const memory = createMemoryDialogueRolloutPort();
    const en = render(
      <I18nProvider initial={EN}>
        <SettingsPage route="#/settings/general" dialoguePort={memory.port} />
      </I18nProvider>,
    );
    const card = await screen.findByTestId("dialogue-rollout-card");
    expect(card).toHaveAttribute("data-dialogue-default", "off");
    expect(card).toHaveAttribute("data-write-gate", "open");
    expect(card).toHaveTextContent("Off by default");
    expect(card).toHaveTextContent("original slot rules");
    expect(card).toHaveTextContent("command journal stays");
    expect(card).toHaveTextContent("Packages ship this off");
    expect(screen.getByTestId("dialogue-rollout-enabled")).not.toBeChecked();
    expect(card.textContent ?? "").not.toMatch(/[\u3400-\u9fff]/);
    fireEvent.click(screen.getByTestId("dialogue-rollout-enabled"));
    expect(memory.state.saves).toEqual([true]);
    expect(screen.getByTestId("dialogue-rollout-enabled")).toBeChecked();
    en.unmount();

    const zhMemory = createMemoryDialogueRolloutPort({gateClosed: true, gateReason: "duplicate_m"});
    render(
      <I18nProvider initial={ZH}>
        <DialogueRolloutCard port={zhMemory.port} />
      </I18nProvider>,
    );
    const zh = await screen.findByTestId("dialogue-rollout-card");
    expect(zh).toHaveAttribute("data-write-gate", "closed");
    expect(zh).toHaveTextContent("对话驱动研究");
    expect(zh).toHaveTextContent("写入口已关闭：duplicate_m");
    expect(zh).toHaveTextContent("命令 journal 仍保留");
  });
});

describe("evidence grade line", () => {
  it("renders the same exploratory grade the API would send", () => {
    render(
      <I18nProvider initial={EN}>
        <EvidenceGradeNote
          grade={{
            grade: "exploratory",
            reason: "成分名单晚于探索截止日，只能作为探索级",
          }}
        />
      </I18nProvider>,
    );
    const line = screen.getByTestId("evidence-grade");
    expect(line).toHaveAttribute("data-grade", "exploratory");
    expect(line).toHaveTextContent("Exploratory — research record only");
    expect(screen.getByTestId("evidence-grade-reason")).toHaveTextContent("成分名单晚于探索截止日");
  });
});
