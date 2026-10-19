import {renderHook, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import type {DesktopView} from "./contracts";
import {RUN_START_RITUAL_MS} from "./runStartRitual";
import {useRunStartRitual} from "./useRunStartRitual";

const settings = {
  thesis: "t",
  universe: "u",
  max_effective_hours: "12h",
  round1_methods: "m",
  coverage_floor: "c",
};

const confirm: DesktopView = {
  kind: "confirm_run",
  researchId: "r-1",
  dialogue: [],
  settings,
};

const running: DesktopView = {
  kind: "running",
  researchId: "r-1",
  status: "running",
  version: 2,
  effective: "3h12 / 12h",
  coverage: "ok",
  rounds: [],
};

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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useRunStartRitual", () => {
  it("activates briefly on confirm_run → running", async () => {
    mockMatchMedia(false);
    const {result, rerender} = renderHook(
      ({view}: {view: DesktopView}) => useRunStartRitual(view),
      {initialProps: {view: confirm as DesktopView}},
    );
    expect(result.current).toBe(false);
    rerender({view: running});
    expect(result.current).toBe(true);
    await waitFor(
      () => expect(result.current).toBe(false),
      {timeout: RUN_START_RITUAL_MS + 200},
    );
  });

  it("stays inactive when prefers-reduced-motion", () => {
    mockMatchMedia(true);
    const {result, rerender} = renderHook(
      ({view}: {view: DesktopView}) => useRunStartRitual(view),
      {initialProps: {view: confirm as DesktopView}},
    );
    rerender({view: running});
    expect(result.current).toBe(false);
  });
});
