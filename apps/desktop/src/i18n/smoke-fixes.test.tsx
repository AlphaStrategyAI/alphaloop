import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import type {DesktopApi, DesktopView} from "../contracts";
import {I18nProvider} from "./I18nProvider";
import {enCatalog} from "./catalog";
import {CompletedScreen} from "../screens/CompletedScreen";
import {ConfirmRunCard} from "../screens/ConfirmRunScreen";

const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};
const CJK_PUNCT = /[。，、；：！？「」『』（）〈〉《》【】‘’]/;

afterEach(() => cleanup());

function api(): DesktopApi {
  return {
    fetchView: vi.fn(),
    createDraft: vi.fn(),
    confirmRun: vi.fn(),
    setResearchSymbol: vi.fn(async () => undefined),
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

const singleName = {
  count: 1,
  listName: "用户指定标的",
  listVersion: "user",
  summaryLine: "1 只 · 用户指定标的 · 已覆盖默认的池",
  overrideNote: "已覆盖默认的池",
  symbols: ["600519.SH"],
  source: "user_override" as const,
  dataStart: "2016-10-20",
  dataEnd: "2026-10-19",
  dataCutoff: "2026-10-19",
  dataSource: "AkShare 日线（新浪优先）",
};

function leaves(value: unknown, prefix = ""): Array<[string, string]> {
  if (typeof value === "string") return [[prefix, value]];
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
      leaves(child, prefix ? `${prefix}.${key}` : key),
    );
  }
  return [];
}

describe("I2 smoke follow-ups", () => {
  it("keeps Chinese punctuation and curly apostrophes out of English pit and copy strings", () => {
    for (const [key, text] of [...leaves(enCatalog.ui.pit, "ui.pit"), ...leaves(enCatalog.ui.copy, "ui.copy")]) {
      expect(text, key).not.toMatch(CJK_PUNCT);
    }
    expect(enCatalog.ui.copy.pitScope).toContain("source's");
  });

  it("uses an English period between conclusion materials sentences", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-pit",
      status: "completed",
      title: "600519",
      selectedRoundId: "round-1",
      selectedMethodId: "pit.consistency",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
      pitDetail: {
        executed: true,
        passed: true,
        evidenceUsed: 0,
        undatedExcluded: [],
        scope: "只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订",
        note: "未引用外部资料",
      },
    };
    render(
      <I18nProvider initial={EN}>
        <CompletedScreen api={api()} view={view} />
      </I18nProvider>,
    );
    const detail = screen.getByTestId("pit-detail").textContent ?? "";
    expect(detail).toContain("publication date. Checks only that a source's publication date");
    expect(detail).not.toMatch(CJK_PUNCT);
    expect(detail).not.toMatch(/source\s+'|'\s+s/);
  });

  it("translates a single-name user list on the confirm card and the conclusion page", () => {
    const confirm: DesktopView = {
      kind: "confirm_run",
      researchId: "r-one",
      dialogue: [],
      chatEnabled: false,
      settings: {
        thesis: "关注 600519.SH",
        universe: "A股 · 股票",
        max_effective_hours: "4 小时",
        round1_methods: "分段稳健性检验",
        coverage_floor: "至少 1 个标的",
      },
      symbolSelection: singleName,
    };
    const {unmount} = render(
      <I18nProvider initial={EN}>
        <ConfirmRunCard api={api()} view={confirm} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("symbol-selection-summary")).toHaveTextContent(
      "1 name · User-specified symbols · Replaced the default universe",
    );
    expect(screen.getByTestId("symbol-selection-summary").textContent).not.toMatch(/[\u4e00-\u9fff]/);
    unmount();

    const completed: DesktopView = {
      kind: "completed",
      researchId: "r-one",
      status: "completed",
      title: "关注 600519.SH",
      selectedRoundId: "round-1",
      selectedMethodId: "m-1",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: false,
      },
      symbolSelection: singleName,
    };
    render(
      <I18nProvider initial={EN}>
        <CompletedScreen api={api()} view={completed} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("completed-symbol-selection-summary")).toHaveTextContent(
      "1 name · User-specified symbols · Replaced the default universe",
    );
    expect(screen.getByTestId("completed-symbol-selection-summary").textContent).not.toMatch(/[\u4e00-\u9fff]/);
  });
});

