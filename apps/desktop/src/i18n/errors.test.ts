import {describe, expect, it} from "vitest";

import {ERROR_CODES} from "./conventions";
import {enCatalog, zhCatalog} from "./catalog";
import {localizeError} from "./errors";
import {lookupMessage} from "./translate";

describe("error codes", () => {
  it("has a catalog sentence for every contracted code", () => {
    for (const code of Object.keys(ERROR_CODES)) {
      expect(lookupMessage(zhCatalog, `errors.codes.${code}`)).toBeTruthy();
      expect(lookupMessage(enCatalog, `errors.codes.${code}`)).toBeTruthy();
    }
  });

  it("keeps the migrated Chinese sentences equal to the legacy engine text", () => {
    for (const [code, spec] of Object.entries(ERROR_CODES)) {
      if (code === "contact_email_missing") continue;
      expect(lookupMessage(zhCatalog, `errors.codes.${code}`)).toBe(spec.legacyZh);
    }
  });

  it("shows a generic explanation for an unknown code and keeps the raw text in details", () => {
    const localized = localizeError("zh", {
      code: "NO_SUCH_CODE",
      message: "error sending request for url…",
      detail: "error sending request for url…",
    });
    expect(localized.unmapped).toBe(true);
    expect(localized.summary).not.toContain("NO_SUCH_CODE");
    expect(localized.summary).not.toContain("errors.unmapped");
    expect(localized.summary).not.toContain("error sending request");
    expect(localized.detail).toContain("NO_SUCH_CODE");
    expect(localized.detail).toContain("error sending request for url…");
    expect(localized.next).toBeTruthy();
  });

  it("localizes a known code and does not translate technical details", () => {
    const localized = localizeError("zh", {
      code: "DATA_EMPTY_PRICES",
      message: "数据源未返回行情，请检查标的和网络。",
      detail: "error sending request for url…",
    });
    expect(localized.unmapped).toBe(false);
    expect(localized.summary).toBe("数据源未返回行情，请检查标的和网络。");
    expect(localized.summary).not.toContain("errors.codes");
    expect(localized.detail).toBe("error sending request for url…");
  });

  it("renders the symbol errors in zh and en", () => {
    expect(localizeError("zh", {code: "SYMBOL_UNRESOLVED", params: {token: "900901"}}).summary).toBe(
      "无法确认「900901」属于哪个交易所。请选择交易所，或输入带后缀的完整代码。",
    );
    expect(localizeError("en", {code: "SYMBOL_UNRESOLVED", params: {token: "900901"}}).summary).toBe(
      "Can't tell which exchange “900901” trades on. Pick an exchange or enter the full code with its suffix.",
    );
    expect(localizeError("zh", {code: "SYMBOL_NO_DATA", params: {symbol: "609999.SH"}}).summary).toBe(
      "所选数据源没有 609999.SH 的行情，无法开跑。请改代码或换数据源。",
    );
    expect(localizeError("en", {code: "SYMBOL_NO_DATA", params: {symbol: "609999.SH"}}).summary).toBe(
      "The selected data source has no data for 609999.SH, so the run can't start. Change the symbol or the data source.",
    );
    expect(localizeError("zh", {code: "SYMBOL_EDIT_NOT_DRAFT"}).summary).toBe(
      "只有草稿上的确认卡可以改标的。",
    );
    expect(localizeError("en", {code: "SYMBOL_EDIT_NOT_DRAFT"}).summary).toBe(
      "Only a draft's confirm card can change the symbol.",
    );
    expect(localizeError("zh", {code: "SYMBOL_ETF_UNSUPPORTED", params: {symbol: "510300.SH"}}).summary).toBe(
      "所选数据源暂不支持 A 股 ETF 行情（510300.SH），无法开跑。",
    );
    expect(localizeError("en", {code: "SYMBOL_ETF_UNSUPPORTED", params: {symbol: "510300.SH"}}).summary).toBe(
      "The selected data source doesn't support China A-share ETF prices yet (510300.SH), so the run can't start.",
    );
    expect(localizeError("zh", {code: "SYMBOL_ASK_PENDING"}).summary).toBe("先确认上面的代码再开跑。");
    expect(localizeError("en", {code: "SYMBOL_ASK_PENDING"}).summary).toBe(
      "Confirm the symbols above before running.",
    );
    expect(
      localizeError("zh", {
        code: "SYMBOL_MIXED_MARKETS",
        params: {cn_symbols: "600519.SH", us_symbols: "SPY"},
      }).summary,
    ).toBe("一次研究只能用同一个市场的标的，这里既有 A 股（600519.SH），也有美股（SPY）。请删掉其中一边。");
    expect(
      localizeError("en", {
        code: "SYMBOL_MIXED_MARKETS",
        params: {cn_symbols: "600519.SH", us_symbols: "SPY"},
      }).summary,
    ).toBe(
      "A study can only use symbols from one market, but this has both China A-shares (600519.SH) and US stocks (SPY). Remove one side.",
    );
  });

  it("leaves a legacy message without a code unchanged", () => {
    const localized = localizeError("en", {message: "UNIQUE constraint failed"});
    expect(localized.summary).toBe("UNIQUE constraint failed");
    expect(localized.detail).toBeNull();
    expect(localized.unmapped).toBe(false);
  });
});
