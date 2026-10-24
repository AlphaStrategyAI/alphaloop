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

function list(title: string): Extract<DesktopView, {kind: "research_list"}> {
  return {
    kind: "research_list",
    rows: [{id: "r-old", title, status: "draft"}],
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
});
