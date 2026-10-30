import {describe, expect, it} from "vitest";

import {enCatalog, isFinalMessageKey, zhCatalog} from "./catalog";
import {localizeKnownCopy} from "./productCopy";
import {translate} from "./translate";

const zh = (text: string) => localizeKnownCopy(text, (key, params) => translate("zh", key, params));
const en = (text: string) => localizeKnownCopy(text, (key, params) => translate("en", key, params));

function leaves(value: unknown, prefix = ""): Array<[string, string]> {
  if (typeof value === "string") return [[prefix, value]];
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
      leaves(child, prefix ? `${prefix}.${key}` : key),
    );
  }
  return [];
}

const EXHAUSTED =
  "本窗口所有研究累计 1 轮；轮数越多，偶然通过的可能性越高。未通过门禁：市场计分卡。只能导出研究记录包。可点「继续迭代」追加预算后再跑（阈值不变）。";
const US_LIST = "美股大市值池 · 503 只 · 名单日 2026-10-16";
const CN_LIST = "A 股大市值池 · 300 只 · 名单日 2026-10-19";
const V1_LINE = "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池";

describe("repeated misunderstanding", () => {
  it("shows the apology once when the engine stacked it", () => {
    const stacked = "没能理解你的意思。没能理解你的意思。最多允许多少有效研究时间？例如：12 小时，或 30 分钟。暂停和等待确认不计时。";
    const once = en(stacked);
    expect(once.match(/I couldn't understand that/g)).toHaveLength(1);
    expect(once).toContain("30 minutes");
    expect(once).not.toMatch(/没能理解/);
  });
});

describe("catalog keys for secrets and previously hardcoded product copy", () => {
  it("keeps the signed-off same-token finance ask final", () => {
    expect(isFinalMessageKey("ui.confirm.financeAskSame")).toBe(true);
    expect(zhCatalog.ui.confirm.financeAskSame).toBe(
      "{{symbol}} 是美股代码，也是金融缩写。要把它当作标的吗？",
    );
    expect(enCatalog.ui.confirm.financeAskSame).toBe(
      "{{symbol}} is a US ticker and also a finance abbreviation. Use it as a symbol?",
    );
  });

  it("uses a half-width space in every zh UI string that names A-shares", () => {
    for (const [key, text] of leaves(zhCatalog)) {
      expect(text, key).not.toMatch(/A股/);
    }
    expect(zh("A股 · 股票")).toBe("A 股 · 股票");
    expect(zh("A 股 · 股票")).toBe("A 股 · 股票");
    expect(en("A股 · 股票")).toBe("China A-shares · equities");
    expect(en("A 股 · 股票")).toBe("China A-shares · equities");
  });

  it("keeps the secrets rail and panel strings in both languages", () => {
    expect(translate("zh", "ui.secrets.open")).toBe("密钥");
    expect(translate("en", "ui.secrets.open")).toBe("Keys");
    expect(translate("en", "ui.secrets.title")).toBe("Keys");
    expect(translate("zh", "ui.secrets.locked")).toBe("口令文件已在，需要解锁。");
    expect(translate("en", "ui.secrets.locked")).toBe("A passphrase file is present and needs to be unlocked.");
    expect(translate("zh", "ui.secrets.passphraseFile")).toBe("口令加密的本机文件");
    expect(translate("en", "ui.secrets.needsChoice")).toContain("Secret Service");
    expect(translate("zh", "ui.secrets.saved")).toBe("已保存。界面不保留明文。");
  });

  it("leaves Chinese product sentences unchanged and translates them in English", () => {
    expect(zh(US_LIST)).toBe(US_LIST);
    expect(en(US_LIST)).toBe("US large-cap universe · 503 names · list date 2026-10-16");
    expect(zh(CN_LIST)).toBe(CN_LIST);
    expect(en(CN_LIST)).toBe("China A-share large-cap universe · 300 names · list date 2026-10-19");
    expect(enCatalog.ui.copy.cnLarge).toBe(
      enCatalog.ui.copy.usLarge.replace("US large-cap", "China A-share large-cap"),
    );
    expect(zh("取自标普 500 在名单日的成分，非时点成分")).toBe("取自标普 500 在名单日的成分，非时点成分");
    expect(en("取自沪深 300 在名单日的成分，非时点成分")).toBe(
      "Based on CSI 300 membership on the list date; not point-in-time.",
    );
    const survivorshipZh = "股票池是名单日的成分，回看更早的历史含幸存者偏差。";
    expect(zh(survivorshipZh)).toBe(survivorshipZh);
    expect(en(survivorshipZh)).toBe("Uses list-date members; earlier history has survivorship bias.");
    expect(translate("en", "ui.copy.cnLarge", {count: 300, date: "2026-10-19"})).toBe(
      "China A-share large-cap universe · 300 names · list date 2026-10-19",
    );
    for (const key of ["ui.copy.cnLarge", "ui.copy.cnLargeNote", "ui.copy.survivorshipHint"] as const) {
      expect(isFinalMessageKey(key), key).toBe(true);
      const text = translate("en", key, {count: 300, date: "2026-10-19"});
      expect(text, key).not.toMatch(/[\u3000-\u303F\uFF00-\uFFEF]/);
      expect(text, key).not.toMatch(/[。，、；：！？「」『』（）‘’]/);
    }
    const csiKeys = leaves(enCatalog)
      .filter(([, text]) => text.includes("CSI 300"))
      .map(([key]) => key);
    expect(csiKeys).toEqual(["ui.copy.cnLargeNote", "ui.glossaryBody.benchmark"]);
    expect(zh(V1_LINE)).toBe(V1_LINE);
    expect(en(V1_LINE)).toBe("40 names · US large-cap · version 1 · 2026-10-17 · default universe");
    expect(zh(EXHAUSTED)).toBe(EXHAUSTED);
    expect(en(EXHAUSTED)).not.toMatch(/[\u4e00-\u9fff]/);
    expect(en(EXHAUSTED)).toContain("Market scorecard");
    expect(zh("「分段稳健性检验」重验未通过。")).toBe("「分段稳健性检验」重验未通过。");
    expect(en("「分段稳健性检验」重验未通过。")).toBe("“Subperiod robustness check” re-verification did not pass.");
    expect(zh("未模拟 T+1 与涨跌停，实际成交可能更差")).toBe("未模拟 T+1 与涨跌停，实际成交可能更差");
    expect(en("0.00 小时")).toBe("0 seconds");
    expect(zh("0.00 小时")).toBe("0 秒");
    expect(en("0.0833333 小时")).toBe("5 min");
    expect(zh("0.0833333 小时")).toBe("5 分钟");
    expect(en("4 小时")).toBe("4 h");
    expect(zh("4 小时")).toBe("4 小时");
    expect(en("1.5 小时")).toBe("1 h 30 min");
    expect(zh("1.5 小时")).toBe("1 小时 30 分钟");
    expect(en("至少 1 个标的")).toBe("At least 1 name");
    expect(en("至少 0 个标的")).toBe("At least 0 names");
    expect(en("至少 2 个标的")).toBe("At least 2 names");
    expect(en("至少 1 个标的、10 年、缺失不超过 5%")).toBe(
      "At least 1 name, 10 years of data, missing no more than 5%",
    );
    const floorOne = "至少 1 个标的、3 年数据，缺失不超过 5%";
    expect(zh(floorOne)).toBe(floorOne);
    expect(en(floorOne)).toBe("At least 1 name, 3 years of data, missing no more than 5%");
    expect(en("至少 25 个标的、10 年数据，缺失不超过 5%")).toBe(
      "At least 25 names, 10 years of data, missing no more than 5%",
    );
    expect(en("当前 1 个标的、3 年数据，缺失 0%")).toBe("Now 1 name, 3 years of data, 0% missing");
    expect(translate("en", "ui.copy.usLarge", {count: 1, date: "2026-10-16"})).toBe(
      "US large-cap universe · 1 name · list date 2026-10-16",
    );
    expect(translate("en", "ui.copy.cnLarge", {count: 300, date: "2026-10-19"})).toBe(
      "China A-share large-cap universe · 300 names · list date 2026-10-19",
    );
    expect(translate("zh", "ui.copy.coverageFloor", {assets: 1, years: 3, missing: 5})).toBe(
      "至少 1 个标的、3 年数据，缺失不超过 5%",
    );
    expect(en("因缺少行情数据，已从标的池剔除 1 只，剩余 1 只可用于本轮研究。")).toBe(
      "Missing prices removed 1 name from the universe. 1 name remains for this round.",
    );
    expect(translate("en", "ui.confirm.summary", {count: 1, listName: "List", listVersion: "2", pool: ""})).toBe(
      "1 symbol · list List · version 2",
    );
    expect(translate("en", "errors.codes.MARKET_DATA_TIMEOUT", {symbol_count: 1})).toBe(
      "Timed out before 1 name finished. Try again.",
    );
    const singleName = "1 只 · 用户指定标的 · 已覆盖默认的池";
    expect(zh(singleName)).toBe(singleName);
    expect(en(singleName)).toBe("1 name · User-specified symbols · Replaced the default universe");
    expect(en(singleName)).not.toMatch(/[\u4e00-\u9fff]/);
    const initialSpec = "模型变更：初始 均值回归 规格";
    expect(zh(initialSpec)).toBe(initialSpec);
    expect(en(initialSpec)).toBe("Model changes: Initial mean reversion spec");
    expect(en(initialSpec)).not.toMatch(/[\u4e00-\u9fff]/);
    const scope = translate("en", "ui.copy.pitScope");
    expect(scope).toBe(
      "Checks only that a source's publication date is on or before the backtest cutoff. It does not cover the universe, adjustments, or financial revisions.",
    );
    expect(scope).not.toMatch(/[。，、；：！？「」『』（）‘’]/);
    expect(scope).toContain("source's");
    expect(scope).not.toMatch(/source\s+'|'\s+s/);
  });

  it("does not translate a user thesis or a literature title", () => {
    const thesis = "关注 600519.SH 的低波动回归";
    expect(en(thesis)).toBe(thesis);
    const paper = "年份论文";
    expect(en(paper)).toBe(paper);
  });
});
