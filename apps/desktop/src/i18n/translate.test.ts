import {describe, expect, it} from "vitest";

import {enCatalog, zhCatalog} from "./catalog";
import {translate} from "./translate";

describe("missing copy falls back and never shows the key", () => {
  it("uses the other language when the current catalog has no string", () => {
    const catalogs = {
      zh: {only: "只有中文"} as unknown as typeof zhCatalog,
      en: {} as unknown as typeof enCatalog,
    };
    expect(translate("en", "only", undefined, catalogs)).toBe("只有中文");
    expect(translate("zh", "only", undefined, catalogs)).toBe("只有中文");
  });

  it("does not render a raw key when both languages are missing", () => {
    const catalogs = {zh: zhCatalog, en: enCatalog};
    const rendered = translate("zh", "settings.not.a.real.key", undefined, catalogs);
    expect(rendered).not.toContain("settings.not.a.real.key");
    expect(rendered).not.toContain("not.a.real");
    expect(rendered.length).toBeGreaterThan(0);
  });

  it("interpolates parameters", () => {
    expect(translate("zh", "settings.general.followSystem", {languageName: "中文"})).toContain("中文");
  });
});

describe("English plurals", () => {
  const counted = [
    ["ui.completed.iterateFallback", "n", {threshold: 3}, "round", "rounds"],
    ["ui.completed.suspicionBody", "n", {threshold: 3}, "round", "rounds"],
    ["ui.copy.researchThisWindow", "n", {}, "round", "rounds"],
    ["ui.copy.coverageFloor", "assets", {years: 3, missing: 5}, "name", "names"],
    ["ui.copy.coverageFloorShort", "assets", {}, "name", "names"],
    ["ui.confirm.summary", "count", {listName: "List", listVersion: "2", pool: ""}, "symbol", "symbols"],
    ["ui.methods.used", "count", {}, "research", "researches"],
    ["ui.pit.firstViolation", "count", {title: "T", doiPart: "", when: "then", cutoff: "cut"}, "violation", "violations"],
    ["errors.codes.MARKET_DATA_TIMEOUT", "symbol_count", {}, "name", "names"],
    ["ui.copy.versionTrials", "budget", {used: 1}, "round", "rounds"],
  ] as const;

  it("uses one for 1 and other for 0 and 2", () => {
    for (const [key, countName, extra, singular, plural] of counted) {
      const one = translate("en", key, {...extra, [countName]: 1});
      const zero = translate("en", key, {...extra, [countName]: 0});
      const two = translate("en", key, {...extra, [countName]: 2});
      expect(one, key).toContain(`1 ${singular}`);
      expect(one, key).not.toContain(plural);
      expect(zero, key).toContain(`0 ${plural}`);
      expect(two, key).toContain(`2 ${plural}`);
      for (const rendered of [one, zero, two]) {
        expect(rendered, key).not.toMatch(/\{\{|plural|Noun/);
      }
    }
  });

  it("pluralizes years independently of names", () => {
    expect(translate("en", "ui.copy.coverageFloor", {assets: 1, years: 1, missing: 5})).toBe(
      "At least 1 name, 1 year of data, missing no more than 5%",
    );
    expect(translate("en", "ui.copy.coverageFloor", {assets: 2, years: 1, missing: 5})).toBe(
      "At least 2 names, 1 year of data, missing no more than 5%",
    );
    expect(translate("en", "ui.copy.coverageNow", {assets: 0, years: 2, missing: 0})).toBe(
      "Now 0 names, 2 years of data, 0% missing",
    );
  });
});
