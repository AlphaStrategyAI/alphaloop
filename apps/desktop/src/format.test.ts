import {describe, expect, it} from "vitest";

import {formatResearchTimestamp} from "./format";

describe("formatResearchTimestamp", () => {
  it("formats ISO timestamps in a fixed timezone (Asia/Shanghai)", () => {
    const formatted = formatResearchTimestamp("2026-08-28T12:00:00+00:00", "Asia/Shanghai");
    expect(formatted).toBe("2026-08-28 20:00");
    expect(formatted).not.toMatch(/Jan|月|\//);
  });
});
