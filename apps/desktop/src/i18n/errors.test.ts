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
      if (code === "contact_email_missing" || code === "MARKET_DATA_FETCH_FAILED") continue;
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
    expect(localizeError("zh", {code: "SYMBOL_AMOUNT_LIKE", params: {token: "600519", symbol: "600519.SH"}}).summary).toBe(
      "「600519」看起来像金额，也可能是代码 600519.SH。要把它当作标的吗？",
    );
    expect(localizeError("en", {code: "SYMBOL_AMOUNT_LIKE", params: {token: "600519", symbol: "600519.SH"}}).summary).toBe(
      '"600519" looks like an amount, but it could also be the symbol 600519.SH. Use it as a symbol?',
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

  it("localizes too few named symbols in the UI language", () => {
    const params = {count: 1, minimum: 25};
    expect(localizeError("zh", {code: "UNIVERSE_TOO_FEW_SYMBOLS", params}).summary).toBe(
      "当前仅 1 个标的，低于最低覆盖要求的 25 个。请调低覆盖底线或增加标的后再开跑。",
    );
    expect(localizeError("en", {code: "UNIVERSE_TOO_FEW_SYMBOLS", params}).summary).toBe(
      "Only 1 name in this study, below the coverage minimum of 25. Lower the coverage floor or add symbols before running.",
    );
    expect(localizeError("en", {code: "UNIVERSE_TOO_FEW_SYMBOLS", params}).unmapped).toBe(false);
    expect(localizeError("zh", {code: "UNIVERSE_TOO_FEW_SYMBOLS", params: {count: 2, minimum: 25}}).summary).toContain(
      "2",
    );
    expect(localizeError("en", {code: "UNIVERSE_TOO_FEW_SYMBOLS", params: {count: 2, minimum: 25}}).summary).toContain(
      "2 names",
    );
  });

  it("keeps MARKET_DATA_FETCH_FAILED off the main line and in technical details", () => {
    const localized = localizeError("zh", {
      code: "MARKET_DATA_FETCH_FAILED",
      params: {symbol: "600519.SH"},
      message: "provider returned an empty price frame",
      detail: "provider returned an empty price frame",
    });
    expect(localized.summary).toBe("行情没有取到：600519.SH。");
    expect(localized.summary).not.toContain("MARKET_DATA_FETCH_FAILED");
    expect(localized.next).toBe("研究已暂停，本机数据未改。可检查网络或数据源后按当前版本继续。");
    expect(localized.detail).toContain("MARKET_DATA_FETCH_FAILED");
    expect(localized.detail).toContain("provider returned an empty price frame");
    const english = localizeError("en", {
      code: "MARKET_DATA_FETCH_FAILED",
      params: {symbol: "600519.SH"},
      message: "provider returned an empty price frame",
    });
    expect(english.summary).toBe("Couldn't fetch market data for 600519.SH.");
    expect(english.summary).not.toMatch(/[A-Z]{3,}_[A-Z]/);
    expect(english.detail).toContain("MARKET_DATA_FETCH_FAILED");
  });

  it("leaves a legacy message without a code unchanged", () => {
    const localized = localizeError("en", {message: "UNIQUE constraint failed"});
    expect(localized.summary).toBe("UNIQUE constraint failed");
    expect(localized.detail).toBeNull();
    expect(localized.unmapped).toBe(false);
  });
});
