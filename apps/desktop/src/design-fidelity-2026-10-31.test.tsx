import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {formatResearchTimestamp} from "./format";
import {enCatalog, zhCatalog} from "./i18n/catalog";
import {I18nProvider} from "./i18n/I18nProvider";
import {translate} from "./i18n/translate";
import {SettingsPage} from "./settings/SettingsPage";
import {createMemoryLlmSettingsPort} from "./settings/llmSettingsPort";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi();
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

function running(status: "running" | "paused"): DesktopView {
  return {
    kind: "running",
    researchId: "r-1",
    status,
    version: 1,
    effective: "1h",
    coverage: "ok",
    rounds: [],
    currentAction: "查资料",
  };
}

describe("design fidelity 2026-10-31", () => {
  it("uses one display status on paused and running", () => {
    render(<App api={api} initialView={running("paused")} initialRoute="#/research/r-1" />);
    const paused = screen.getByTestId("run-status-title");
    expect(paused).toHaveTextContent("已暂停");
    expect(paused).toHaveAttribute("data-status-truth", "display");
    expect(screen.getByTestId("status-head")).toBeInTheDocument();
    expect(screen.getByTestId("version-orbit")).toHaveTextContent("查资料");
    expect(screen.getByTestId("detail-aside")).toHaveAttribute("data-surface", "deep");
    expect(screen.getByTestId("tech-pulse-atmosphere")).toHaveAttribute("data-atmosphere", "flat");
    cleanup();
    render(<App api={api} initialView={running("running")} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("run-status-title")).toHaveTextContent("运行中");
    expect(screen.getByTestId("status-head")).toBeInTheDocument();
    expect(screen.getByTestId("detail-aside")).toHaveAttribute("data-aside-fill", "#0B0E13");
  });

  it("shows four short gate cards and a cyan research-record export", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "ended",
      title: "均值回归",
      selectedRoundId: "round-1",
      selectedMethodId: "m1",
      eligibility: {
        allMethodsPassed: false,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: false,
      },
      metrics: {excessAnn: -0.055, maxDrawdown: -0.267},
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    const gates = screen.getByTestId("completed-gate-pills");
    expect(gates).toHaveTextContent("门禁");
    expect(gates).toHaveTextContent("待确认");
    expect(gates).toHaveTextContent("重现");
    expect(gates).toHaveTextContent("PIT");
    expect(gates).toHaveTextContent("未过");
    expect(gates).toHaveTextContent("通过");
    expect(gates).toHaveTextContent("验证未全部通过");
    const exportButton = screen.getByTestId("export-research-record-primary");
    expect(exportButton).toHaveClass("cyan-button");
    expect(exportButton).not.toHaveClass("stop-button-primary");
    const metrics = screen.getByTestId("completed-metrics");
    expect(metrics).toHaveAttribute("data-metrics-tier", "title");
    expect(metrics).toHaveAttribute("data-metric-size", "20");
    expect(metrics).toHaveAttribute("data-metric-color", "ink");
  });

  it("keeps settings sections as horizontal tabs under the title", () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/general" />
      </I18nProvider>,
    );
    const tabs = screen.getByRole("navigation", {name: "设置"});
    expect(tabs).toHaveAttribute("data-orientation", "horizontal");
    expect(tabs).toHaveClass("settings-tabs");
    expect(screen.getByRole("heading", {level: 1})).toHaveTextContent("设置 · 通用");
    expect(screen.getByTestId("settings-chrome")).toContainElement(tabs);
  });

  it("uses approved English rail and list labels, not color names", () => {
    expect(translate("en", "ui.status.railHold")).toBe("Paused");
    expect(translate("en", "ui.status.railRun")).toBe("Running");
    expect(translate("en", "ui.status.railStop")).toBe("Done");
    expect(translate("en", "ui.status.railOk")).toBe("Done");
    expect(translate("en", "ui.status.endedShort")).toBe("Failed");
    expect(translate("en", "ui.status.paused")).toBe("Paused");
    expect(enCatalog.ui.list.tagline).toBe("One conversation, one research. Pending confirmation first.");
    expect(zhCatalog.ui.list.tagline).toBe("一条对话，一次研究。等待确认的排最前。");
    for (const label of ["Paused", "Running", "Done", "Failed"] as const) {
      expect(label).not.toMatch(/^(Hold|Stop|Run)$/);
    }
    expect(formatResearchTimestamp("2026-10-19T02:24:00.000Z", "Asia/Shanghai")).toBe("2026-10-19 10:24");
  });

  it("renders the frame-10 LLM disclosure in full", async () => {
    render(
      <I18nProvider initial={{preference: "zh", systemLocale: "zh-CN", resolved: "zh"}}>
        <SettingsPage route="#/settings/llm" llmPort={createMemoryLlmSettingsPort().port} />
      </I18nProvider>,
    );
    const panel = await screen.findByTestId("settings-llm");
    expect(panel).toHaveTextContent("测试连接");
    expect(panel).toHaveTextContent("替换密钥");
    expect(panel).toHaveTextContent("换模型 = 实现层");
    expect(panel).toHaveTextContent("保存前必须看过");
    expect(panel).toHaveTextContent("我已看过会发送和不会发送的内容");
    expect(panel).toHaveTextContent("· 研究论点：大致原理和你的原话。原话按原样发送，里面写到的代码也会发出去");
    expect(panel).toHaveTextContent("· 文献原文");
    expect(panel).toHaveTextContent("不开新版，不弹经济逻辑确认，四关不变。本轮记录写「gpt-4.1 @ api.openai.com」，不写密钥。");
    expect(document.querySelector(".llm-form")).toHaveAttribute("data-focus-ring", "cyan");
  });
});
