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
