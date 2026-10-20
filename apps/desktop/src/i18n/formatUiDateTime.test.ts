import {describe, expect, it} from "vitest";

import {formatUiDate, formatUiDateTime} from "./formatUiDateTime";

describe("formatUiDateTime", () => {
  it("writes YYYY-MM-DD HH:mm in the given time zone", () => {
    expect(formatUiDateTime("2026-10-19T10:00:00.000Z", "Asia/Shanghai")).toBe("2026-10-19 18:00");
    expect(formatUiDateTime("2026-01-01T16:00:00.000Z", "Asia/Shanghai")).toBe("2026-01-02 00:00");
    expect(formatUiDate("2026-10-19T10:00:00.000Z", "Asia/Shanghai")).toBe("2026-10-19");
  });

  it("keeps a calendar day on that day in every zone", () => {
    expect(formatUiDateTime("2026-10-19", "America/Los_Angeles")).toBe("2026-10-19");
    expect(formatUiDate("2026-10-19", "Pacific/Kiritimati")).toBe("2026-10-19");
    expect(formatUiDateTime("2026-10-16", "Asia/Shanghai")).toBe("2026-10-16");
  });

  it("does not use a month name or a slash date", () => {
    const formatted = formatUiDateTime("2026-10-19T10:00:00.000Z", "UTC");
    expect(formatted).toBe("2026-10-19 10:00");
    expect(formatted).not.toMatch(/Jan|月|\//);
  });
});
