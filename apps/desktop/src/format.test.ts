import {describe, expect, it} from "vitest";

import {formatUiDateTime} from "./i18n/formatUiDateTime";
import {formatResearchTimestamp} from "./format";

const INSTANT = "2026-10-19T02:24:00.000Z";

describe("formatResearchTimestamp", () => {
  it("defaults to the resolved machine zone, independent of which zone that is", () => {
    const local = readZone();
    if (local === null) {
      expect(formatResearchTimestamp(INSTANT)).toBe("2026-10-19 02:24Z");
      return;
    }
    expect(formatResearchTimestamp(INSTANT)).toBe(formatUiDateTime(INSTANT, local));
    expect(formatResearchTimestamp(INSTANT)).toBe(formatResearchTimestamp(INSTANT, local));
  });

  it("writes YYYY-MM-DD HH:mm without an offset, and Z only when the zone cannot be read", () => {
    expect(formatResearchTimestamp(INSTANT, "Asia/Shanghai")).toBe("2026-10-19 10:24");
    expect(formatResearchTimestamp("2026-01-15T15:00:00.000Z", "America/New_York")).toBe("2026-01-15 10:00");
    expect(formatResearchTimestamp("2026-10-19T04:54:00.000Z", "Asia/Kolkata")).toBe("2026-10-19 10:24");
    expect(formatResearchTimestamp(INSTANT, "Asia/Shanghai")).not.toContain("+08:00");
    expect(formatResearchTimestamp(INSTANT, null)).toBe("2026-10-19 02:24Z");
  });

  it("returns a calendar day unchanged in every zone", () => {
    expect(formatResearchTimestamp("2026-10-19", "America/Los_Angeles")).toBe("2026-10-19");
    expect(formatResearchTimestamp("2026-10-16", "Asia/Shanghai")).toBe("2026-10-16");
    expect(formatResearchTimestamp("2026-10-18", "Pacific/Kiritimati")).toBe("2026-10-18");
  });
});

function readZone(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!zone) return null;
    new Intl.DateTimeFormat("en-US", {timeZone: zone}).format(0);
    return zone;
  } catch {
    return null;
  }
}
