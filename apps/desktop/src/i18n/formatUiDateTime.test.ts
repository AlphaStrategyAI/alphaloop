import {describe, expect, it} from "vitest";

import {enCatalog, zhCatalog} from "./catalog";
import {formatUiDate, formatUiDateTime} from "./formatUiDateTime";

const INSTANT = "2026-10-19T02:24:00.000Z";

describe("formatUiDateTime", () => {
  it("writes YYYY-MM-DD HH:mm without a numeric offset or zone abbreviation", () => {
    expect(formatUiDateTime(INSTANT, "Asia/Shanghai")).toBe("2026-10-19 10:24");
    expect(formatUiDateTime("2026-01-15T15:00:00.000Z", "America/New_York")).toBe("2026-01-15 10:00");
    expect(formatUiDateTime("2026-10-19T04:54:00.000Z", "Asia/Kolkata")).toBe("2026-10-19 10:24");
    expect(formatUiDateTime(INSTANT, "UTC")).toBe("2026-10-19 02:24");
    for (const zone of ["Asia/Shanghai", "America/New_York", "Asia/Kolkata", "UTC"] as const) {
      expect(formatUiDateTime(INSTANT, zone)).not.toMatch(/[+-]\d{2}:\d{2}|CST|EST|EDT|PST|PDT|GMT|Z/);
    }
  });

  it("follows the daylight-saving transition instead of a fixed offset", () => {
    expect(formatUiDateTime("2026-03-08T06:30:00.000Z", "America/New_York")).toBe("2026-03-08 01:30");
    expect(formatUiDateTime("2026-03-08T07:30:00.000Z", "America/New_York")).toBe("2026-03-08 03:30");
    expect(formatUiDateTime("2026-11-01T05:30:00.000Z", "America/New_York")).toBe("2026-11-01 01:30");
    expect(formatUiDateTime("2026-11-01T06:30:00.000Z", "America/New_York")).toBe("2026-11-01 01:30");
  });

  it("prints UTC with Z when the zone cannot be read", () => {
    expect(formatUiDateTime(INSTANT, null)).toBe("2026-10-19 02:24Z");
  });

  it("keeps a calendar day on that day in every zone", () => {
    expect(formatUiDateTime("2026-10-19", "America/Los_Angeles")).toBe("2026-10-19");
    expect(formatUiDate("2026-10-19", "Pacific/Kiritimati")).toBe("2026-10-19");
    expect(formatUiDateTime("2026-10-16", "Asia/Shanghai")).toBe("2026-10-16");
    expect(formatUiDate("2026-10-19T10:00:00.000Z", "Asia/Shanghai")).toBe("2026-10-19");
  });

  it("uses the same pattern in Chinese and English", () => {
    expect(zhCatalog.format.datePattern).toBe("YYYY-MM-DD");
    expect(zhCatalog.format.dateTimePattern).toBe("YYYY-MM-DD HH:mm");
    expect(enCatalog.format.dateTimePattern).toBe(zhCatalog.format.dateTimePattern);
    expect(enCatalog.format.datePattern).toBe(zhCatalog.format.datePattern);
  });
});
