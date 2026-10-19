import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const methodsView: DesktopView = {
  kind: "methods",
  methods: [{id: "overfit.walk", name: "分段稳健性检验", revision: "walk-v1", description: "分段"}],
};

function makeApi(fetchView: DesktopApi["fetchView"]): DesktopApi {
  return {
    fetchView,
    createDraft: vi.fn(),
    confirmRun: vi.fn(),
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

function go(hash: string) {
  window.location.hash = hash;
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

describe("route failures and rail highlight", () => {
  beforeEach(() => {
    window.location.hash = "#/methods";
  });

  it.each(["#/glossary", "#/research/missing"])(
    "shows the fetch error and a retry instead of loading forever for %s",
    async (hash) => {
      const fetchView = vi.fn(async () => {
        throw new Error(`rejected ${hash}`);
      });
      render(<App api={makeApi(fetchView)} initialView={methodsView} initialRoute="#/methods" />);
      go(hash);
      const alert = await screen.findByTestId("route-error");
      expect(alert).toHaveTextContent(`rejected ${hash}`);
      expect(screen.queryByTestId("route-loading")).not.toBeInTheDocument();
      const callsBeforeRetry = fetchView.mock.calls.length;
      fireEvent.click(screen.getByTestId("route-retry"));
      await waitFor(() => {
        expect(fetchView.mock.calls.length).toBeGreaterThan(callsBeforeRetry);
      });
    },
  );

  it("highlights 术语 from the route while the methods view is still on screen", async () => {
    const fetchView = vi.fn(() => new Promise<DesktopView>(() => undefined));
    render(<App api={makeApi(fetchView)} initialView={methodsView} initialRoute="#/methods" />);
    expect(screen.getByRole("link", {name: "方法库"})).toHaveClass("active");
    go("#/glossary");
    await waitFor(() => {
      expect(screen.getByRole("link", {name: "术语"})).toHaveClass("active");
    });
    expect(screen.getByRole("link", {name: "方法库"})).not.toHaveClass("active");
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "methods");
  });
});
