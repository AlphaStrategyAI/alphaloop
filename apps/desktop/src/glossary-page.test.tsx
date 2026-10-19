import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";

import {App, routeFor} from "./App";
import type {DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const view: DesktopView = {
  kind: "glossary",
  intro: "展示名说明。旧称仍可在对话里解析。",
  entries: [
    {
      id: "overfit.walk",
      term: "分段稳健性检验",
      body: "这是时间分段表现一致性，不是 walk-forward。旧称「走样检验」仍可解析。",
    },
    {
      id: "crowding.load",
      term: "集中度",
      body: "这是权重集中度（非市场拥挤度）。旧称「拥挤度」仍可解析。",
    },
    {
      id: "stability.oos",
      term: "样本外稳定",
      body: "只看样本外各段方向是否同号，和分段稳健性检验不是同一项。",
    },
  ],
};

describe("glossary page", () => {
  it("routes to the glossary hash", () => {
    expect(routeFor(view)).toBe("#/glossary");
  });

  it("shows renamed gates as folds and keeps the glossary nav active", () => {
    render(<App api={minimalDesktopApi()} initialView={view} initialRoute="#/glossary" />);
    expect(screen.getByTestId("glossary-page")).toBeInTheDocument();
    expect(screen.getByRole("link", {name: "术语"})).toHaveClass("active");
    expect(screen.getByRole("link", {name: "研究"})).not.toHaveClass("active");
    const walk = screen.getByText("分段稳健性检验").closest("details");
    const crowd = screen.getByText("集中度").closest("details");
    expect(walk).toHaveAttribute("open");
    expect(walk).toHaveTextContent("walk-forward");
    expect(walk).toHaveTextContent("走样检验");
    expect(crowd).toHaveTextContent("非市场拥挤度");
    expect(crowd).toHaveTextContent("拥挤度");
    expect(screen.getByText("样本外稳定").closest("details")).toHaveTextContent("不是同一项");
  });
});
