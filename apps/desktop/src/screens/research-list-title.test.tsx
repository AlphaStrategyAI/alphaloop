import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import type {DesktopView} from "../contracts";
import {I18nProvider} from "../i18n/I18nProvider";
import {minimalDesktopApi} from "../test-fixtures";
import {ResearchList} from "./ResearchListScreen";

const ZH = {preference: "zh" as const, systemLocale: "zh-CN", resolved: "zh" as const};
const EN = {preference: "en" as const, systemLocale: "en-US", resolved: "en" as const};

afterEach(() => cleanup());

function list(title: string, universeLabel?: string): Extract<DesktopView, {kind: "research_list"}> {
  return {
    kind: "research_list",
    rows: [{id: "r-old", title, status: "draft", universeLabel}],
  };
}

function show(language: typeof ZH | typeof EN, title: string) {
  render(
    <I18nProvider initial={language}>
      <ResearchList api={minimalDesktopApi()} view={list(title)} />
    </I18nProvider>,
  );
  return screen.getByRole("heading", {level: 3});
}

describe("research list titles", () => {
  it("renders a legacy untitled title in both locales", () => {
    expect(show(EN, "未命名研究")).toHaveTextContent("Untitled study");
    cleanup();
    expect(show(ZH, "未命名研究")).toHaveTextContent("未命名研究");
  });

  it("renders an empty stored title as untitled", () => {
    expect(show(EN, "")).toHaveTextContent("Untitled study");
    cleanup();
    expect(show(ZH, "")).toHaveTextContent("未命名研究");
  });

  it("leaves a real thesis unchanged in English", () => {
    expect(show(EN, "美股低波策略")).toHaveTextContent("美股低波策略");
  });

  it("renders an unlocked universe as Not selected", () => {
    render(
      <I18nProvider initial={EN}>
        <ResearchList api={minimalDesktopApi()} view={list("美股低波策略", "待选择")} />
      </I18nProvider>,
    );
    const row = screen.getByTestId("research-row");
    expect(row).toHaveTextContent("Not selected");
    expect(row).not.toHaveTextContent("A 股 · 股票");
    cleanup();
    render(
      <I18nProvider initial={ZH}>
        <ResearchList api={minimalDesktopApi()} view={list("美股低波策略", "待选择")} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("research-row")).toHaveTextContent("待选择");
    cleanup();
    render(
      <I18nProvider initial={EN}>
        <ResearchList api={minimalDesktopApi()} view={list("股债再平衡", "美股 · 基金")} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("research-row")).toHaveTextContent("US · funds");
  });
});
