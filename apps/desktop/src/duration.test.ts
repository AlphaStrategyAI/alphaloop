import {describe, expect, it} from "vitest";

import {formatDuration, formatEngineDuration} from "./duration";
import {translate} from "./i18n/translate";

const en = (key: Parameters<typeof translate>[1], params?: Parameters<typeof translate>[2]) =>
  translate("en", key, params);
const zh = (key: Parameters<typeof translate>[1], params?: Parameters<typeof translate>[2]) =>
  translate("zh", key, params);

describe("formatDuration", () => {
  it("uses seconds, minutes, and hours instead of decimal hours", () => {
    expect(formatDuration(0, en)).toBe("0 seconds");
    expect(formatDuration(1, en)).toBe("1 second");
    expect(formatDuration(7, en)).toBe("7 seconds");
    expect(formatDuration(5 * 60, en)).toBe("5 min");
    expect(formatDuration(90 * 60, en)).toBe("1 h 30 min");
    expect(formatDuration(4 * 3600, en)).toBe("4 h");
    expect(formatDuration(0, zh)).toBe("0 秒");
    expect(formatDuration(1, zh)).toBe("1 秒");
    expect(formatDuration(5 * 60, zh)).toBe("5 分钟");
    expect(formatDuration(90 * 60, zh)).toBe("1 小时 30 分钟");
    expect(formatDuration(4 * 3600, zh)).toBe("4 小时");
  });

  it("reads engine labels, including a 5-minute cap written as a fraction of an hour", () => {
    expect(formatEngineDuration("0.00 小时", en)).toBe("0 seconds");
    expect(formatEngineDuration("0.0833333 小时", en)).toBe("5 min");
    expect(formatEngineDuration("0.0833333 小时", zh)).toBe("5 分钟");
    expect(formatEngineDuration("4h", en)).toBe("4 h");
    expect(formatEngineDuration("4h", zh)).toBe("4 小时");
    expect(formatEngineDuration("3h12", en)).toBe("3 h 12 min");
    expect(formatEngineDuration("7 秒", en)).toBe("7 seconds");
    expect(formatEngineDuration("1 分 30 秒", en)).toBe("1 minute 30 seconds");
    expect(formatEngineDuration("not a duration", en)).toBeNull();
  });
});
