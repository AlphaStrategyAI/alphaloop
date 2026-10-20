import {describe, expect, it} from "vitest";

import {localizeKnownCopy} from "./productCopy";
import {translate} from "./translate";

const zh = (text: string) => localizeKnownCopy(text, (key, params) => translate("zh", key, params));
const en = (text: string) => localizeKnownCopy(text, (key, params) => translate("en", key, params));

const EXHAUSTED =
  "本窗口所有研究累计 1 轮；轮数越多，偶然通过的可能性越高。未通过门禁：市场计分卡。只能导出研究记录包。可点「继续迭代」追加预算后再跑（阈值不变）。";
const US_LIST = "美股大市值池 · 503 只 · 名单日 2026-10-16";
const CN_LIST = "A 股大市值池 · 300 只 · 名单日 2026-10-19";
const V1_LINE = "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池";

describe("catalog keys for secrets and previously hardcoded product copy", () => {
  it("keeps the secrets rail and panel strings in both languages", () => {
    expect(translate("zh", "ui.secrets.open")).toBe("密钥");
    expect(translate("en", "ui.secrets.open")).toBe("Secrets");
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
    expect(zh("取自标普 500 在名单日的成分，非时点成分")).toBe("取自标普 500 在名单日的成分，非时点成分");
    expect(en("取自沪深 300 在名单日的成分，非时点成分")).toBe(
      "Taken from CSI 300 membership on the list date; not point-in-time.",
    );
    expect(zh(V1_LINE)).toBe(V1_LINE);
    expect(en(V1_LINE)).toBe("40 names · US large-cap · version 1 · 2026-10-17 · default universe");
    expect(zh(EXHAUSTED)).toBe(EXHAUSTED);
    expect(en(EXHAUSTED)).not.toMatch(/[\u4e00-\u9fff]/);
    expect(en(EXHAUSTED)).toContain("Market scorecard");
    expect(zh("「分段稳健性检验」重验未通过。")).toBe("「分段稳健性检验」重验未通过。");
    expect(en("「分段稳健性检验」重验未通过。")).toBe("“Subperiod robustness check” re-verification did not pass.");
    expect(zh("未模拟 T+1 与涨跌停，实际成交可能更差")).toBe("未模拟 T+1 与涨跌停，实际成交可能更差");
    expect(en("0.00 小时")).toBe("0.00 hours");
    expect(zh("0.00 小时")).toBe("0.00 小时");
  });

  it("does not translate a user thesis or a literature title", () => {
    const thesis = "关注 600519.SH 的低波动回归";
    expect(en(thesis)).toBe(thesis);
    const paper = "年份论文";
    expect(en(paper)).toBe(paper);
  });
});
