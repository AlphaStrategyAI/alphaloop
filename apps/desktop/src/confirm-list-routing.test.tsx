import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

afterEach(() => cleanup());

const settingsFor = (thesis: string) => ({
  thesis,
  universe: "美股 · 股票",
  max_effective_hours: "4 小时",
  round1_methods: "走样检验",
  coverage_floor: "至少 25 个标的",
});

const listView: DesktopView = {
  kind: "research_list",
  awaiting: {
    id: "r-wait-new",
    title: "Newer awaiting",
    status: "awaiting_confirm",
    universeLabel: "美股 · 股票",
  },
  rows: [
    {
      id: "r-confirm-new",
      title: "Newer confirm",
      status: "confirm_run",
      universeLabel: "美股 · 股票",
    },
    {
      id: "r-confirm-old",
      title: "Older confirm",
      status: "confirm_run",
      universeLabel: "A股 · 股票",
    },
    {
      id: "r-wait-old",
      title: "Older awaiting",
      status: "awaiting_confirm",
      universeLabel: "A股 · 股票",
    },
    {id: "r-run", title: "Still running", status: "running"},
  ],
};

function confirmView(researchId: string, thesis: string): DesktopView {
  return {
    kind: "confirm_run",
    researchId,
    dialogue: [],
    settings: settingsFor(thesis),
  };
}

function awaitingView(researchId: string, proposed: string): DesktopView {
  return {
    kind: "awaiting_confirm",
    researchId,
    version: 1,
    proposed,
    reason: "because",
    effect: "effect",
  };
}

const views: Record<string, DesktopView> = {
  "#/research": listView,
  "#/research/r-confirm-new": confirmView("r-confirm-new", "thesis-confirm-new"),
  "#/research/r-confirm-old": confirmView("r-confirm-old", "thesis-confirm-old"),
  "#/research/r-wait-new": awaitingView("r-wait-new", "proposed-wait-new"),
  "#/research/r-wait-old": awaitingView("r-wait-old", "proposed-wait-old"),
};

function makeApi(fetchView: DesktopApi["fetchView"]): DesktopApi {
  return {
    fetchView,
    createDraft: vi.fn(async () => "r-new"),
    confirmRun: vi.fn(async () => undefined),
    setResearchSymbol: vi.fn(async () => undefined),
  answerSymbolAsk: vi.fn(async () => undefined),
  useHintedSymbol: vi.fn(async () => undefined),
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

function openCard(researchId: string) {
  const card = document.querySelector(`article[data-research-id="${researchId}"]`);
  expect(card).not.toBeNull();
  const link = within(card as HTMLElement).getByRole("link", {name: "打开确认卡"});
  expect(link).toHaveAttribute("href", `#/research/${researchId}`);
  expect(link).toHaveAttribute("data-research-id", researchId);
  fireEvent.click(link);
  expect(window.location.hash).toBe(`#/research/${researchId}`);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

describe("multiple confirm cards stay bound to their research id", () => {
  beforeEach(() => {
    window.location.hash = "#/research";
  });

  it("lists every confirm_run and awaiting_confirm research", () => {
    render(<App api={makeApi(vi.fn(async () => listView))} initialView={listView} initialRoute="#/research" />);

    const confirmCards = screen.getAllByTestId("confirm-pinned-card");
    expect(confirmCards.map((card) => card.getAttribute("data-research-id"))).toEqual([
      "r-confirm-new",
      "r-confirm-old",
    ]);
    expect(confirmCards.map((card) => card.querySelector("h2")?.textContent)).toEqual([
      "Newer confirm",
      "Older confirm",
    ]);

    const awaitingCards = screen.getAllByTestId("awaiting-pinned-card");
    expect(awaitingCards.map((card) => card.getAttribute("data-research-id"))).toEqual([
      "r-wait-new",
      "r-wait-old",
    ]);
    expect(screen.getAllByTestId("research-row")).toHaveLength(1);
    expect(screen.getByText("Still running")).toBeInTheDocument();
  });

  it("opens the confirm card for the research that was clicked", async () => {
    const fetchView = vi.fn(async (route: string) => views[route] ?? listView);
    render(
      <App api={makeApi(fetchView)} initialView={listView} initialRoute="#/research" />,
    );

    openCard("r-confirm-old");
    await waitFor(() => {
      expect(fetchView).toHaveBeenCalledWith("#/research/r-confirm-old");
    });
    await waitFor(() => {
      expect(screen.getByText("thesis-confirm-old")).toBeInTheDocument();
    });
    expect(screen.queryByText("thesis-confirm-new")).not.toBeInTheDocument();
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "confirm_run");

    window.location.hash = "#/research";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await waitFor(() => {
      expect(screen.getAllByTestId("confirm-pinned-card")).toHaveLength(2);
    });

    openCard("r-wait-old");
    await waitFor(() => {
      expect(fetchView).toHaveBeenCalledWith("#/research/r-wait-old");
    });
    await waitFor(() => {
      expect(screen.getByText("proposed-wait-old")).toBeInTheDocument();
    });
    expect(screen.queryByText("proposed-wait-new")).not.toBeInTheDocument();
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", "awaiting_confirm");
  });

  it("does not show a confirm card whose research id differs from the route", async () => {
    let resolveOld: (view: DesktopView) => void = () => undefined;
    const fetchView = vi.fn((route: string) => {
      if (route === "#/research/r-confirm-old") {
        return new Promise<DesktopView>((resolve) => {
          resolveOld = resolve;
        });
      }
      return Promise.resolve(listView);
    });
    render(
      <App api={makeApi(fetchView)} initialView={listView} initialRoute="#/research" />,
    );

    openCard("r-confirm-old");
    await waitFor(() => {
      expect(fetchView).toHaveBeenCalledWith("#/research/r-confirm-old");
    });
    resolveOld(confirmView("r-confirm-new", "thesis-confirm-new"));
    await waitFor(() => {
      expect(screen.getByTestId("route-loading")).toBeInTheDocument();
    });
    expect(screen.queryByText("thesis-confirm-new")).not.toBeInTheDocument();
    expect(screen.getByTestId("night-shell")).not.toHaveAttribute("data-view", "confirm_run");
  });
});
