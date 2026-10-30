import {describe, expect, it} from "vitest";

import {matchesResearchListFilter} from "./listStatusDisplay";

describe("matchesResearchListFilter", () => {
  it("keeps every status on All", () => {
    expect(matchesResearchListFilter("draft", "all")).toBe(true);
    expect(matchesResearchListFilter("confirm_run", "all")).toBe(true);
    expect(matchesResearchListFilter("ended", "all")).toBe(true);
  });

  it("groups both confirm surfaces under Pending and both finished statuses under Done", () => {
    expect(matchesResearchListFilter("awaiting_confirm", "pending")).toBe(true);
    expect(matchesResearchListFilter("confirm_run", "pending")).toBe(true);
    expect(matchesResearchListFilter("running", "pending")).toBe(false);
    expect(matchesResearchListFilter("completed", "done")).toBe(true);
    expect(matchesResearchListFilter("ended", "done")).toBe(true);
    expect(matchesResearchListFilter("paused", "done")).toBe(false);
  });

  it("matches running, paused, and draft exactly", () => {
    expect(matchesResearchListFilter("running", "running")).toBe(true);
    expect(matchesResearchListFilter("paused", "paused")).toBe(true);
    expect(matchesResearchListFilter("draft", "draft")).toBe(true);
    expect(matchesResearchListFilter("draft", "running")).toBe(false);
  });
});
