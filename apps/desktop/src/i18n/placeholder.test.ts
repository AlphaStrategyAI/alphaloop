import {describe, expect, it} from "vitest";

import lockedGlossary from "./locked-glossary.json";
import {enCatalog, isFinalMessageKey, zhCatalog} from "./catalog";
import {PLACEHOLDER_MARKER} from "./conventions";
import {containsPlaceholderMarker} from "./placeholder";

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
  it("recognizes the searchable marker and ignores final copy", () => {
    expect(containsPlaceholderMarker(`${PLACEHOLDER_MARKER} Hello`)).toBe(true);
    expect(containsPlaceholderMarker("Strategy family")).toBe(false);
    expect(containsPlaceholderMarker("Technical details")).toBe(false);
  });

  it("marks non-final English and keeps locked glossary terms unmarked", () => {
    const zhKeys = leaves(zhCatalog).map(([key]) => key).sort();
    const enLeaves = leaves(enCatalog);
    expect(enLeaves.map(([key]) => key).sort()).toEqual(zhKeys);
    for (const [key, text] of enLeaves) {
      expect(text).not.toBe(key);
      if (isFinalMessageKey(key)) {
        expect(containsPlaceholderMarker(text), key).toBe(false);
      } else {
        expect(containsPlaceholderMarker(text), key).toBe(true);
      }
    }
    for (const [key, entry] of Object.entries(lockedGlossary)) {
      expect(enCatalog.glossary[key as keyof typeof enCatalog.glossary]).toBe(entry.en);
      expect(containsPlaceholderMarker(entry.en)).toBe(false);
    }
  });
});
