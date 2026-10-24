import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {routeFromHash} from "./routing";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const listView: DesktopView = {
  kind: "research_list",
  rows: [
    {id: "r-detail", title: "详情页研究", status: "draft", universeLabel: "A股 · 股票"},
  ],
};

const detailView: DesktopView = {
  kind: "draft",
  researchId: "r-detail",
  dialogue: [{role: "user", text: "hello"}],
  settings: {
    thesis: "测试",
    universe: "A股 · 股票",
    max_effective_hours: "8 小时",
    round1_methods: "分段稳健性检验",
    coverage_floor: "至少 1 个标的、10 年数据，缺失不超过 5%",
  },
};

const methodsView: DesktopView = {
  kind: "methods",
  selected: "m1",
  methods: [{id: "m1", name: "分段稳健性检验", revision: "v1", description: "desc"}],
};

function makeApi(fetchView: DesktopApi["fetchView"]): DesktopApi {
  return {
    fetchView,
    createDraft: vi.fn(async () => "r-new"),
    confirmRun: vi.fn(async () => undefined),
    setResearchSymbol: vi.fn(async () => undefined),
  answerSymbolAsk: vi.fn(async () => undefined),
  useHintedSymbol: vi.fn(async () => undefined),
  revertSymbolAsk: vi.fn(async () => undefined),
  removeMarketSide: vi.fn(async () => undefined),
    unlockBrief: vi.fn(async () => undefined),
    sendDialogue: vi.fn(async () => undefined),
    pauseResearch: vi.fn(async () => undefined),
    resumeResearch: vi.fn(async () => undefined),
    confirmModification: vi.fn(async () => undefined),
    continueIterate: vi.fn(async () => undefined),
    extendResearch: vi.fn(async () => undefined),
    deleteResearch: vi.fn(async () => undefined),
    resolveConfirm: vi.fn(async () => undefined),
    exportArtifact: vi.fn(async () => "/tmp/export.zip"),
    revealExportInFolder: vi.fn(async () => undefined),
    reverify: vi.fn(async () => undefined),
    reviseMethod: vi.fn(async () => undefined),
    createMethod: vi.fn(async () => undefined),
  };
}

function navigateHash(route: string) {
  const hash = route.startsWith("#") ? route : `#${route}`;
  window.location.hash = hash;
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

describe("hash-driven navigation", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("routeFromHash normalizes empty hash to research list", () => {
    expect(routeFromHash("")).toBe("#/research");
    expect(routeFromHash("#")).toBe("#/research");
    expect(routeFromHash("#/research/r-1")).toBe("#/research/r-1");
  });

  it("loads detail view when initialRoute is a research id", async () => {
    const fetchView = vi.fn(async (route: string) => {
      if (route === "#/research/r-detail") return detailView;
      return listView;
    });
    render(
      <App
        api={makeApi(fetchView)}
        initialView={listView}
        initialRoute="#/research/r-detail"
      />,
    );
    await waitFor(() => {
      expect(fetchView).toHaveBeenCalledWith("#/research/r-detail");
    });
    await waitFor(() => {
      expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "draft");
    });
  });

  it("clicking 进入 updates route and shows target view; back returns to list", async () => {
    const fetchView = vi.fn(async (route: string) => {
      if (route === "#/research/r-detail") return detailView;
      return listView;
    });
    render(<App api={makeApi(fetchView)} initialView={listView} initialRoute="#/research" />);
    await waitFor(() => expect(fetchView).toHaveBeenCalledWith("#/research"));

    const enter = screen.getByRole("link", {name: "进入"});
    fireEvent.click(enter);
    navigateHash("#/research/r-detail");

    await waitFor(() => {
      expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "draft");
    });
    expect(screen.getByText("hello")).toBeInTheDocument();

    navigateHash("#/research");
    await waitFor(() => {
      expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "research_list");
    });
  });

  it("polling keeps fetching the current hash route (no snap back to list)", async () => {
    vi.useFakeTimers();
    window.location.hash = "#/research/r-detail";
    const fetchView = vi.fn(async (route: string) => {
      if (route === "#/research/r-detail") return detailView;
      return listView;
    });
    render(
      <App
        api={makeApi(fetchView)}
        initialView={detailView}
        initialRoute="#/research/r-detail"
      />,
    );
    await vi.advanceTimersByTimeAsync(0);
    const routesAfterPoll = fetchView.mock.calls.map((call) => call[0]);
    expect(routesAfterPoll.length).toBeGreaterThan(0);
    expect(routesAfterPoll.every((r) => r === "#/research/r-detail")).toBe(true);

    await vi.advanceTimersByTimeAsync(2_000);
    const laterRoutes = fetchView.mock.calls.map((call) => call[0]);
    expect(laterRoutes.every((r) => r === "#/research/r-detail")).toBe(true);
  });

  it("navigates to methods via rail link", async () => {
    const fetchView = vi.fn(async (route: string) => {
      if (route.startsWith("#/methods")) return methodsView;
      return listView;
    });
    render(<App api={makeApi(fetchView)} initialView={listView} initialRoute="#/research" />);
    fireEvent.click(screen.getByRole("link", {name: "方法库"}));
    navigateHash("#/methods");

    await waitFor(() => {
      expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "methods");
    });
    expect(fetchView).toHaveBeenCalledWith("#/methods");
  });
});
