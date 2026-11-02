import {describe, expect, it} from "vitest";

import {enCatalog, isFinalMessageKey, zhCatalog} from "./catalog";
import {isCatalogSentence, localizeKnownCopy} from "./productCopy";
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

const POLICY_SUMMARY =
  "实现层只调整回看天数（10、15、20）和入场 Z 值（1、1.5、2），从 15 日、z=1 起步，最多 5 轮。去重按参数、实现修订、交易成本、方法和输入哈希，不含尝试编号和解释。停止条件：候选耗尽、重复、全绿通过、时间预算、轮次上限。";
const POLICY_LEGACY = "这一版沿用原先的回看期 +5 规则。";
const POLICY_ENGLISH =
  "The implementation layer only adjusts lookback days (10, 15, 20) and entry Z (1, 1.5, 2), starting from 15 days at z=1, for at most 5 rounds. Dedup uses the parameters, the implementation revision, trading costs, methods, and the input hash. It leaves out the attempt number and the explanation. Stop conditions: candidates exhausted, duplicate, all checks passed, time budget, round cap.";

describe("confirm-run policy copy", () => {
  it("keeps Chinese product labels and translates the same sentence to English", () => {
    expect(zh(POLICY_SUMMARY)).toBe(POLICY_SUMMARY);
    expect(zh(POLICY_SUMMARY)).not.toMatch(/lookback_days|entry_z|time_budget|round_cap|all_pass|\bexhausted\b/);
    expect(en(POLICY_SUMMARY)).toBe(POLICY_ENGLISH);
    expect(en(POLICY_SUMMARY)).not.toMatch(/[\u3400-\u9fff]/);
    expect(en(POLICY_SUMMARY)).not.toMatch(/[。，、；：！？「」『』（）‘’]/);
    expect(en(POLICY_SUMMARY)).not.toMatch(/lookback_days|entry_z|time_budget|round_cap/);
    expect(zh(POLICY_LEGACY)).toBe(POLICY_LEGACY);
    expect(en(POLICY_LEGACY)).toBe("This version keeps the previous lookback +5 rule.");
    expect(en(POLICY_LEGACY)).not.toMatch(/[\u3400-\u9fff]/);
    for (const key of [
      "ui.copy.candidatePolicy",
      "ui.copy.candidatePolicyLegacy",
      "ui.copy.policyStopExhausted",
      "ui.copy.policyStopRepeat",
      "ui.copy.policyStopAllPass",
      "ui.copy.policyStopTimeBudget",
      "ui.copy.policyStopRoundCap",
    ] as const) {
      expect(isFinalMessageKey(key), key).toBe(true);
      expect(translate("en", key, {
        lookback: "lookback days",
        entry: "entry Z",
        lookbacks: "10, 15, 20",
        entries: "1, 1.5, 2",
        startDays: 15,
        startZ: "1",
        rounds: 5,
        stops: "candidates exhausted",
      }), key).not.toMatch(/[\u3400-\u9fff]/);
    }
  });
});

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
    expect(en("走样检验、样本外稳定")).toBe("Subperiod robustness check, Out-of-sample stability");
    expect(en("美股股票 AAPL 的均值回归")).toBe("美股股票 AAPL 的均值回归");
    expect(en("至少 1 个标的、10 年、缺失不超过 5%")).toBe(
      "At least 1 name, 10 years of data, missing no more than 5%",
    );
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

  it("translates system proposal sentences and leaves the user's own words", () => {
    const system = [
      "日频截面均值回归（前一日信号）。未支持的限制不会悄悄删掉。",
      "原来的说法不会照原样执行。改成均值回归后，赚的是价格偏离后的回归，不是原来的趋势或突破。",
      "去掉未支持的限制后，实际执行的是日频均值回归，和原话不是同一个含义。",
      "“便宜”会改变策略含义。你指的是价格相对近期的偏离，还是估值便宜？还没说明之前，不会当成你已经同意均值回归。",
      "同行业比较和第三天卖出，当前引擎做不到。若改成不带这两条的均值回归，含义会变。要这样继续，还是先保留原话？",
      "开跑要在确认卡上核对这份提议后再按。附件或这句话不能代替确认。",
      "模型没有给出可用的提议，下面仍按字段提问。",
      "有些限制当前做不到。请确认是否改变含义后再开跑。",
      "“便宜”还没说清是价格偏离还是估值。说清之前不能开跑。",
      "这份提议已经过期。请再核对设定，确认后才能开跑。",
      "数据源和提议里写的不一样。先核对来源，再确认开跑。",
      "报价现在不可用。等数据恢复，或改用有报价的标的后再开跑。",
      "你说的原来的时长和现在记下的不一样。要改成哪一个？",
      "这句话同时有美股和 A 股。一次研究只能留一个市场。",
      "没有本地资料。公开检索只会使用白名单里的家族词，不会把原话发给资料源。",
      "这句话点了两个行情源。要换成哪一个？",
      "只在同行业内比较",
      "引擎没有行业相对比较。这条限制会保留，不会悄悄删掉。",
      "第三天卖出",
      "引擎没有固定第 N 天卖出。这条限制会保留，不会悄悄删掉。",
      "趋势、动量和突破不能在这里执行。原话会保留，不会改写成均值回归。",
    ];
    const proposalKeys = [
      "ui.proposal.executableMeanReversion",
      "ui.proposal.meaningRepick",
      "ui.proposal.meaningWaived",
      "ui.proposal.cheapQuestion",
      "ui.proposal.capabilityQuestion",
      "ui.proposal.runNow",
      "ui.proposal.llmFallback",
      "ui.proposal.capabilityUnresolved",
      "ui.proposal.meaningUnresolved",
      "ui.proposal.stale",
      "ui.proposal.sourceChanged",
      "ui.proposal.quotesUnavailable",
      "ui.proposal.hourConflict",
      "ui.proposal.mixedMarkets",
      "ui.proposal.noMaterials",
      "ui.proposal.twoSources",
      "ui.proposal.industryConstraint",
      "ui.proposal.industryNote",
      "ui.proposal.holdingConstraint",
      "ui.proposal.holdingNote",
      "ui.proposal.momentumNote",
    ] as const;
    for (const key of proposalKeys) {
      expect(isFinalMessageKey(key), key).toBe(true);
      expect(translate("en", key), key).not.toMatch(/[\u3400-\u9fff]/);
    }
    for (const sentence of system) {
      expect(isCatalogSentence(sentence), sentence).toBe(true);
      const english = en(sentence);
      expect(english, sentence).not.toBe(sentence);
      expect(english, sentence).not.toMatch(/[\u3400-\u9fff]/);
      expect(english, sentence).not.toMatch(/[。，、；：！？「」『』（）‘’]/);
      expect(zh(sentence)).toBe(sentence);
      for (const banned of [
        "Continue with mean reversion",
        "Continue as mean reversion",
        "How much effective research time",
      ]) {
        expect(english, sentence).not.toContain(banned);
      }
    }
    const original = "美股股票 AAPL 的均值回归";
    expect(isCatalogSentence(original)).toBe(false);
    expect(en(original)).toBe(original);
    expect(isCatalogSentence("美股动量策略")).toBe(false);
  });
});
