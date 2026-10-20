import {describe, expect, it} from "vitest";

import lockedGlossary from "./locked-glossary.json";
import {enCatalog, isFinalMessageKey, zhCatalog} from "./catalog";
import {PLACEHOLDER_ATTRIBUTE} from "./conventions";
import {isPlaceholderMessageKey} from "./I18nText";
import {containsPlaceholderMarker} from "./placeholder";

const LEGACY_PREFIX = "«i18n-placeholder»";

export function placeholderEnglishCount(): number {
  return leaves(enCatalog).filter(([key]) => isPlaceholderMessageKey(key)).length;
}

function leaves(value: unknown, prefix = ""): Array<[string, string]> {
  if (typeof value === "string") return [[prefix, value]];
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
      leaves(child, prefix ? `${prefix}.${key}` : key),
    );
  }
  return [];
}

describe("placeholder marker", () => {
  it("counts unfinished English from the key manifest, not a body prefix", () => {
    expect(placeholderEnglishCount()).toBeGreaterThan(0);
    expect(PLACEHOLDER_ATTRIBUTE).toBe("data-i18n-placeholder");
    for (const [, text] of leaves(enCatalog)) {
      expect(text).not.toContain(LEGACY_PREFIX);
    }
  });

  it("recognizes a leftover prefix and ignores final copy", () => {
    expect(containsPlaceholderMarker(`${LEGACY_PREFIX} Hello`)).toBe(true);
    expect(containsPlaceholderMarker("Strategy family")).toBe(false);
    expect(containsPlaceholderMarker("Technical details")).toBe(false);
  });

  it("keeps unfinished English the same width as the final sentence", () => {
    const zhKeys = leaves(zhCatalog).map(([key]) => key).sort();
    const enLeaves = leaves(enCatalog);
    expect(enLeaves.map(([key]) => key).sort()).toEqual(zhKeys);
    for (const [key, text] of enLeaves) {
      expect(text).not.toBe(key);
      expect(text.startsWith(LEGACY_PREFIX), key).toBe(false);
      if (isFinalMessageKey(key)) {
        expect(isPlaceholderMessageKey(key), key).toBe(false);
      } else {
        expect(isPlaceholderMessageKey(key), key).toBe(true);
      }
    }
    for (const [key, entry] of Object.entries(lockedGlossary)) {
      expect(enCatalog.glossary[key as keyof typeof enCatalog.glossary]).toBe(entry.en);
      expect(entry.en).not.toContain(LEGACY_PREFIX);
    }
  });
});
