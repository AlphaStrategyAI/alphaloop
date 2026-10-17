import {describe, expect, it} from "vitest";

import {formatResearchTimestamp} from "./format";

describe("formatResearchTimestamp", () => {
  it("formats ISO timestamps in a fixed timezone (Asia/Shanghai)", () => {
    const formatted = formatResearchTimestamp("2026-08-28T12:00:00+00:00", "Asia/Shanghai");
    expect(formatted).toMatch(/2026/);
    expect(formatted).toMatch(/08/);
    expect(formatted).toMatch(/28/);
    expect(formatted).toContain("20:00");
  });
});
