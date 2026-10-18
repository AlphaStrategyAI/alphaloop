import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi({createDraft: vi.fn(async () => "r")});

const settings = {
  thesis: "",
  universe: "",
  max_effective_hours: "",
  round1_methods: "",
  coverage_floor: "",
};

describe("draft polish", () => {
  it("renders system intro before dialogue turns", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [
        {role: "user", text: "你好"},
        {role: "assistant", text: "回复"},
      ],
      settings,
    };
    render(<App api={api} initialView={view} />);
    const intro = screen.getByTestId("dialogue-system-intro");
    const turns = screen.getAllByTestId("dialogue-turn");
    expect(intro.compareDocumentPosition(turns[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("你好").className).toContain("user");
    expect(screen.getByText("回复").className).toContain("assistant");
  });

  it("keeps A-share tickers in thesis from breaking at the dot", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [],
      settings: {...settings, thesis: "关注 600519.SH 与 000001.SZ"},
    };
    render(<App api={api} initialView={view} />);
    const thesis = screen.getByTestId("brief-thesis-value");
    expect(thesis.querySelector(".cn-ticker-nowrap")).toHaveTextContent("600519.SH");
    expect(thesis.querySelectorAll(".cn-ticker-nowrap")).toHaveLength(2);
  });

  it("keeps thesis text in settings from breaking mid-word when possible", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [],
      settings: {...settings, thesis: "均值回归"},
    };
    render(<App api={api} initialView={view} />);
    const thesis = screen.getByTestId("brief-thesis-value");
    expect(thesis).toHaveClass("settings-value-prose");
    expect(thesis).toHaveTextContent("均值回归");
  });

  it("does not show stray trailing slot label in dialogue bubbles", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [{role: "assistant", text: "美股低波动回归"}],
      settings,
    };
    render(<App api={api} initialView={view} />);
    expect(screen.queryByText(/，大致原理/)).not.toBeInTheDocument();
  });
});
