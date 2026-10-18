import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {fireEvent, waitFor} from "@testing-library/react";

import {App, AwaitingConfirmCard, ConfirmRunCard} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";
import {minimalDesktopApi} from "./test-fixtures";
import {RUN_START_RITUAL_MS} from "./runStartRitual";

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation(() => ({
      matches,
      media: "(prefers-reduced-motion: reduce)",
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
      onchange: null,
    })),
  });
}

afterEach(() => cleanup());

const settings = {
  thesis: "关注 600519.SH",
  universe: "A股",
  max_effective_hours: "12h",
  round1_methods: "走样",
  coverage_floor: "8年",
};

const api = minimalDesktopApi({});

describe("Tech Pulse UI", () => {
  it("renders v2 brand mark in the sidebar", () => {
    const view: DesktopView = {kind: "research_list", rows: []};
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("brand-mark").querySelector("img")).toBeTruthy();
  });

  it("renders list workshop chrome", () => {
    render(<App api={api} initialView={{kind: "research_list", rows: []}} />);
    expect(screen.getByText("本机工坊")).toBeInTheDocument();
    expect(screen.getByText(/一条对话/)).toBeInTheDocument();
  });

  it("renders confirm card pulse chrome", () => {
    const view: DesktopView = {
      kind: "confirm_run",
      researchId: "r-1",
      dialogue: [],
      settings,
    };
    render(<ConfirmRunCard api={api} view={view} />);
    expect(screen.getByTestId("confirm-run-card")).toHaveClass("tech-pulse-card");
    expect(screen.getByRole("heading", {name: "确认开跑"})).toBeInTheDocument();
  });

  it("renders running orbit and quota only with parseable effective string", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 2,
      effective: "3h12 / 12h",
      coverage: "覆盖仍在底线之上",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("version-orbit")).toHaveTextContent("v2");
    expect(screen.getByTestId("effective-quota-progress")).toBeInTheDocument();
  });

  it("hides quota progress when effective has no total (no fake meter)", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 1,
      effective: "3.00h",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    expect(screen.queryByTestId("effective-quota-progress")).not.toBeInTheDocument();
  });

  it("renders awaiting confirm pulse card", () => {
    const view: DesktopView = {
      kind: "awaiting_confirm",
      researchId: "r-1",
      version: 2,
      confirmKind: "economic",
      proposed: "改",
      reason: "因",
      effect: "果",
    };
    render(<AwaitingConfirmCard api={api} view={view} />);
    expect(screen.getByTestId("awaiting-confirm-card")).toHaveClass("tech-pulse-card");
  });

  it("keeps A-share ticker nowrap in thesis", () => {
    const view: DesktopView = {
      kind: "draft",
      researchId: "r-1",
      dialogue: [],
      settings,
    };
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("brief-thesis-value").querySelector(".cn-ticker-nowrap")).toHaveTextContent(
      "600519.SH",
    );
  });

  it("renders completed export-ready chrome when eligible", () => {
    const view: DesktopView = {
      kind: "completed",
      researchId: "r-1",
      status: "completed",
      title: "低波动量价回归",
      selectedRoundId: "r1",
      selectedMethodId: "m1",
      eligibility: {
        allMethodsPassed: true,
        noPendingConfirm: true,
        reverifiesPassed: true,
        pitExecutedAndPassed: true,
      },
    };
    render(<App api={api} initialView={view} initialRoute="#/research/r-1" />);
    expect(screen.getByTestId("completed-screen")).toBeInTheDocument();
    expect(screen.getByTestId("export-ready-eyebrow")).toBeInTheDocument();
  });

  it("applies run-start ritual on confirm → running without fake progress UI", async () => {
    mockMatchMedia(false);
    const confirmView: DesktopView = {
      kind: "confirm_run",
      researchId: "r-ritual",
      dialogue: [],
      settings,
    };
    const runningView: DesktopView = {
      kind: "running",
      researchId: "r-ritual",
      status: "running",
      version: 1,
      effective: "1h / 12h",
      coverage: "ok",
      rounds: [],
    };

    let current: DesktopView = confirmView;
    const ritualApi = minimalDesktopApi({
      fetchView: vi.fn(async () => current),
      confirmRun: vi.fn(async () => {
        current = runningView;
      }),
    });

    render(<App api={ritualApi} initialView={confirmView} initialRoute="#/research/r-ritual" />);
    fireEvent.click(screen.getByRole("button", {name: "确认开跑"}));
    await waitFor(() => expect(screen.getByTestId("running-screen")).toBeInTheDocument());
    await waitFor(() =>
      expect(document.querySelector('[data-run-start-ritual="active"]')).toBeTruthy(),
    );
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/X\/N/i)).not.toBeInTheDocument();
    await waitFor(
      () => expect(document.querySelector('[data-run-start-ritual="active"]')).toBeFalsy(),
      {timeout: RUN_START_RITUAL_MS + 300},
    );
  });

  it("does not show placeholder round labels on the version orbit", () => {
    const running: DesktopView = {
      kind: "running",
      researchId: "r-1",
      status: "running",
      version: 2,
      effective: "1h / 12h",
      coverage: "ok",
      rounds: [],
    };
    render(<App api={api} initialView={running} initialRoute="#/research/r-1" />);
    const orbit = screen.getByTestId("version-orbit");
    expect(orbit.textContent).not.toMatch(/X\/N/i);
    expect(orbit).toHaveTextContent("v2");
  });
});
