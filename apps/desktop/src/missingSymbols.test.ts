import {describe, expect, it} from "vitest";

import {enCatalog, zhCatalog} from "./i18n/catalog";
import {missingSymbolsError} from "./missingSymbols";

const zh = zhCatalog.errors.codes.DATA_SYMBOLS_EMPTY;
const en = enCatalog.errors.codes.DATA_SYMBOLS_EMPTY;

describe("missing symbols gate", () => {
  it("matches the engine code", () => {
    expect(missingSymbolsError({code: "DATA_SYMBOLS_EMPTY", message: "other"})).toBe(true);
  });

  it("matches a code-less payload that stored the catalog sentence", () => {
    expect(missingSymbolsError({message: zh})).toBe(true);
    expect(missingSymbolsError({message: en})).toBe(true);
  });

  it("matches the shorter classified sentence, which is the catalog's first sentence", () => {
    const lead = zh.slice(0, zh.search(/[。.]/) + 1);
    expect(lead.length).toBeGreaterThan(8);
    expect(missingSymbolsError({message: lead})).toBe(true);
  });

  it("does not treat a different run error as a missing ticker", () => {
    expect(missingSymbolsError({code: "DATA_EMPTY_PRICES", message: zhCatalog.errors.codes.DATA_EMPTY_PRICES})).toBe(false);
    expect(missingSymbolsError({message: "UNIQUE constraint failed"})).toBe(false);
    expect(missingSymbolsError(null)).toBe(false);
  });
});
