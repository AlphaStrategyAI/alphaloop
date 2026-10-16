import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi();

describe("method library UI", () => {
  it("marks the selected method link active, not always the first", () => {
    const view: DesktopView = {
      kind: "methods",
      selected: "second.method",
      methods: [
        {id: "scorecard.market", name: "市场计分卡", revision: "a".repeat(64), description: "d1"},
        {id: "second.method", name: "第二项", revision: "b".repeat(64), description: "d2"},
      ],
    };
    render(<App api={api} initialView={view} initialRoute="#/methods/second.method" />);
    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.includes("/methods/"));
    const active = links.find((a) => a.classList.contains("active"));
    expect(active?.textContent).toContain("第二项");
    expect(links[0].classList.contains("active")).toBe(false);
    const revision = screen.getAllByTitle("b".repeat(64))[0];
    expect(revision).toHaveTextContent(`${"b".repeat(8)}…`);
  });
});
