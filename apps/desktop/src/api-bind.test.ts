import {describe, expect, it, vi} from "vitest";

import {bindDesktopApi} from "./api-bind";
import type {DesktopApi, DesktopView} from "./contracts";

const listView: DesktopView = {kind: "research_list", rows: []};

describe("bindDesktopApi", () => {
  it("shows mutation errors and refreshes after success", async () => {
    const fetchView = vi.fn(async () => listView);
    const unlockBrief = vi.fn(async () => undefined);
    const api: DesktopApi = {
      fetchView,
      createDraft: vi.fn(),
      confirmRun: vi.fn(),
      unlockBrief,
      sendDialogue: vi.fn(),
      pauseResearch: vi.fn(),
      resumeResearch: vi.fn(),
      confirmModification: vi.fn(),
      continueIterate: vi.fn(),
      extendResearch: vi.fn(),
      deleteResearch: vi.fn(),
      resolveConfirm: vi.fn(),
      exportArtifact: vi.fn(),
      reverify: vi.fn(),
      reviseMethod: vi.fn(),
      createMethod: vi.fn(),
    };
    const onError = vi.fn();
    const refresh = vi.fn(async () => undefined);
    const bound = bindDesktopApi(api, {onError, refresh});

    await bound.unlockBrief("r-1");
    expect(unlockBrief).toHaveBeenCalledWith("r-1");
    expect(refresh).toHaveBeenCalled();

    const failing = vi.fn(async () => {
      throw new Error("HTTP 400");
    });
    const boundFail = bindDesktopApi(
      {...api, unlockBrief: failing},
      {onError, refresh: vi.fn()},
    );
    await expect(boundFail.unlockBrief("r-1")).rejects.toThrow("HTTP 400");
    expect(onError).toHaveBeenCalledWith("HTTP 400");
  });
});
