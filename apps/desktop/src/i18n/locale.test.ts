import {describe, expect, it} from "vitest";

import fixtureJson from "../../../../tests/fixtures/ui_language_cases.json";
import {languageFromSystemLocale, languageName, resolveUiLanguage} from "./locale";

const fixture = fixtureJson as {
  systemTags: Array<{id: string; tag: string | null; language: "zh" | "en"}>;
  resolution: Array<{id: string; preference: string | null; system: string | null; resolved: "zh" | "en"}>;
};

describe("follow system", () => {
  it("maps system tags the same way as the shared fixture", () => {
    for (const item of fixture.systemTags) {
      expect(languageFromSystemLocale(item.tag), item.id).toBe(item.language);
    }
  });

  it("resolves the three preferences without treating an unknown value as a language", () => {
    for (const item of fixture.resolution) {
      expect(resolveUiLanguage(item.preference, item.system), item.id).toBe(item.resolved);
    }
  });

  it("keeps the language names in their own writing", () => {
    expect(languageName("zh")).toBe("中文");
    expect(languageName("en")).toBe("English");
  });
});
