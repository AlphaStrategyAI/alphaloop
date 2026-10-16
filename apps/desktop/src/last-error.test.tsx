import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";

afterEach(() => cleanup());

const api = minimalDesktopApi();

describe("lastError", () => {
  it("renders on paused running view", () => {
    const view: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "paused",
      version: 1,
      effective: "1h",
      coverage: "至少 1 个标的、5 年数据，缺失不超过 20%",
      rounds: [],
      lastError: {message: "UNIQUE constraint failed", count: 3},
    };
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("last-run-error")).toHaveTextContent("UNIQUE constraint failed");
    expect(screen.getByTestId("last-run-error")).toHaveTextContent("3 次");
  });
});
