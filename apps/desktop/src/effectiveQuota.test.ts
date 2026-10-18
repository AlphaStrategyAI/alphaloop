import {describe, expect, it} from "vitest";

import {parseEffectiveQuota} from "./effectiveQuota";

describe("parseEffectiveQuota", () => {
  it("parses slash-separated hour labels from engine", () => {
    const quota = parseEffectiveQuota("3h12 / 12h");
    expect(quota).not.toBeNull();
    expect(quota?.usedLabel).toBe("3h12");
    expect(quota?.totalLabel).toBe("12h");
    expect(quota?.ratio).toBeCloseTo((3 * 60 + 12) / (12 * 60), 3);
  });

  it("returns null when total is unknown (no fake progress)", () => {
    expect(parseEffectiveQuota("3.00h")).toBeNull();
    expect(parseEffectiveQuota(undefined)).toBeNull();
  });
});
