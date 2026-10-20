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

  it("leaves a legacy message without a code unchanged", () => {
    const localized = localizeError("en", {message: "UNIQUE constraint failed"});
    expect(localized.summary).toBe("UNIQUE constraint failed");
    expect(localized.detail).toBeNull();
    expect(localized.unmapped).toBe(false);
  });
});
