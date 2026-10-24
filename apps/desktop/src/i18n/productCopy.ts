import {formatEngineDuration} from "../duration";
import type {MessageKey} from "./I18nProvider";
import type {MessageParams} from "./translate";

export type CopyFn = (key: MessageKey, params?: MessageParams) => string;

const EXACT: Record<string, MessageKey> = {
  "研究已完成，可导出策略包": "ui.copy.headlineExport",
  "研究已完成，但未通过可实盘交接": "ui.copy.headlineHandoff",
  "研究已结束，验证未通过": "ui.copy.headlineFailed",
  "当前冻结验证已全部通过（含时点第四关）。可导出策略包；alphaloop 不提供执行入口。": "ui.copy.summaryEligible",
  "取自标普 500 在名单日的成分，非时点成分": "ui.copy.usLargeNote",
  "取自沪深 300 在名单日的成分，非时点成分": "ui.copy.cnLargeNote",
  "股票池是名单日的成分，回看更早的历史含幸存者偏差。": "ui.copy.survivorshipHint",
  "雅虎日线": "ui.copy.yahoo",
  "AkShare 日线（新浪优先）": "ui.copy.akshare",
  "未模拟 T+1 与涨跌停，实际成交可能更差": "ui.copy.cnExecution",
  "策略族：均值回归（V1 唯一）· 论点文字仅作记录，不改变策略": "ui.copy.meanReversionCard",
  "暂不支持。不推荐最接近的族，不推荐均值回归。动量是第二批首个新增族": "ui.copy.momentumUnsupported",
  "只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订": "ui.copy.pitScope",
  "未引用外部资料": "ui.copy.pitNoExternal",
  "时点一致性未通过，暂不能导出策略包": "ui.copy.blockPitFailed",
  "时点一致性未执行，暂不能导出策略包": "ui.copy.blockPitMissing",
  "公开资料与本机材料": "ui.running.sourcesFallback",
  "公开资料已落成本机材料": "ui.copy.sourcesSaved",
  "未找到相关资料": "ui.copy.noRelevantMaterials",
  "待选择": "ui.confirm.sourcePending",
  "有效研究时间计入「运行中」状态下的采集、建模与验证执行；暂停、等待确认与列表轮询间隔不计入。": "ui.copy.effectiveHint",
  "未锁定": "ui.list.unlocked",
  "查资料": "ui.copy.actionGather",
  "补细节": "ui.copy.actionSpecify",
  "历史模拟": "ui.copy.actionSimulate",
  "迭代": "ui.copy.actionIterate",
  "验证": "glossary.verification",
  "这些是界面和导出包里使用的展示名。方法的 id 与修订号没有改，计算也没有改。对话里仍可输入旧称，会解析成同一个方法。": "ui.copy.glossaryIntro",
};

/** Longer labels first so a prefix does not swallow a more specific name. */
const LABELS: ReadonlyArray<readonly [string, MessageKey]> = [
  ["时点一致性未通过或未执行", "ui.copy.gatePit"],
  ["冻结验证方法未全部通过", "ui.copy.gateMethods"],
  ["重新验证未全部通过", "ui.copy.gateReverify"],
  ["美股大市值（版本 1）", "ui.copy.usLargeV1"],
  ["A股大市值（版本 1）", "ui.copy.cnLargeV1"],
  ["分段稳健性检验", "ui.copy.walk"],
  ["研究状态未完成", "ui.copy.gateCompleted"],
  ["冻结验证方法集", "ui.copy.frozenSet"],
  ["已覆盖默认的池", "ui.copy.overrideDefault"],
  ["用户指定标的", "ui.copy.userSpecified"],
  ["样本外稳定", "ui.copy.oos"],
  ["默认标的池", "ui.copy.defaultTail"],
  ["仍有待确认项", "ui.copy.gatePending"],
  ["美股大市值", "ui.copy.usLargeShort"],
  ["A股大市值", "ui.copy.cnLargeShort"],
  ["市场计分卡", "ui.copy.scorecard"],
  ["时点一致性", "ui.copy.pit"],
  ["换手成本", "ui.copy.turnover"],
  ["已选标的", "ui.copy.selected"],
  ["冻结验证", "ui.copy.frozen"],
  ["回看天数", "ui.copy.lookback"],
  ["入场 Z 值", "ui.copy.entryZ"],
  ["信号定义", "ui.copy.signal"],
  ["特征集", "ui.copy.features"],
  ["模型族", "ui.copy.modelFamily"],
  ["均值回归", "ui.copy.meanReversion"],
  ["集中度", "ui.copy.crowding"],
];

const SHRINK = /^因缺少行情数据，已从标的池剔除 (\d+) 只，剩余 (\d+) 只可用于本轮研究。(?: (.*))?$/;

type Rule = {
  re: RegExp;
  render: (match: RegExpMatchArray, t: CopyFn) => string;
};

function exactLabel(token: string, t: CopyFn): string {
  for (const [zh, key] of LABELS) {
    if (token === zh) return t(key);
  }
  return token;
}

function gateToken(token: string, t: CopyFn): string {
  const trimmed = token.trim();
  for (const [zh, key] of LABELS) {
    if (trimmed === zh) return t(key);
    if (trimmed.startsWith(`${zh} `) || trimmed.startsWith(`${zh}(`)) {
      return `${t(key)}${trimmed.slice(zh.length)}`;
    }
  }
  return trimmed;
}

function gates(raw: string, t: CopyFn): string {
  return raw.split("、").map((part) => gateToken(part, t)).join(t("ui.copy.gateJoiner"));
}

function coverageSentence(
  kind: "now" | "floor",
  assets: string,
  years: string,
  missing: string,
  t: CopyFn,
): string {
  const key = kind === "now" ? "ui.copy.coverageNow" : "ui.copy.coverageFloor";
  return t(key, {assets, years, missing});
}

function paramPiece(piece: string, t: CopyFn): string {
  const trimmed = piece.trim();
  const match = /^(.+?)：(.*) → (.*)$/.exec(trimmed);
  if (match) {
    return t("ui.copy.paramChange", {
      name: exactLabel(match[1], t),
      before: match[2],
      after: match[3],
    });
  }
  const initial = /^初始 (.+) 规格$/.exec(trimmed);
  if (initial) {
    return t("ui.copy.initialSpec", {family: exactLabel(initial[1].trim(), t)});
  }
  return exactLabel(trimmed, t);
}

const RULES: Rule[] = [
  {
    re: /^美股大市值池 · (\d+) 只 · 名单日 (\d{4}-\d{2}-\d{2})$/,
    render: (m, t) => t("ui.copy.usLarge", {count: m[1], date: m[2]}),
  },
  {
    re: /^A 股大市值池 · (\d+) 只 · 名单日 (\d{4}-\d{2}-\d{2})$/,
    render: (m, t) => t("ui.copy.cnLarge", {count: m[1], date: m[2]}),
  },
  {
    re: /^(\d+) 只 · (.+?) · 版本 ([^·]+?) · (\d{4}-\d{2}-\d{2}) · (.+)$/,
    render: (m, t) => t("ui.copy.v1Line", {
      count: m[1],
      listName: exactLabel(m[2], t),
      version: m[3].trim(),
      date: m[4],
      tail: exactLabel(m[5], t),
    }),
  },
  {
    re: /^(\d+) 只 · ([^·]+) · ([^·]+)$/,
    render: (m, t) => t("ui.copy.userLine", {
      count: m[1],
      listName: exactLabel(m[2], t),
      tail: exactLabel(m[3], t),
    }),
  },
  {
    re: /^本窗口所有研究累计 (\d+) 轮；轮数越多，偶然通过的可能性越高。未通过门禁：(.+)。只能导出研究记录包。可点「继续迭代」追加预算后再跑（阈值不变）。$/,
    render: (m, t) => t("ui.copy.summaryExhausted", {
      window: t("ui.completed.iterateFallback", {n: m[1]}),
      gates: gates(m[2], t),
    }),
  },
  {
    re: /^验证方法集已通过，但仍只能导出研究记录包。未满足的门禁：(.+)。$/,
    render: (m, t) => t("ui.copy.summaryMethods", {gates: gates(m[1], t)}),
  },
  {
    re: /^不能导出策略包，只能导出研究记录包。未通过的门禁包括：(.+)。$/,
    render: (m, t) => t("ui.copy.summaryFailed", {gates: gates(m[1], t)}),
  },
  {
    re: /^实现层迭代预算已用尽（(\d+)\/(\d+) 轮）。验证仍未通过；只能导出研究记录包。$/,
    render: (m, t) => t("ui.copy.hintExhausted", {used: m[1], budget: m[2]}),
  },
  {
    re: /^第 (\d+)\/(\d+) 轮验证未通过（未通过：(.+)）。可导出研究记录包。$/,
    render: (m, t) => t("ui.copy.hintRounds", {used: m[1], budget: m[2], gates: gates(m[3], t)}),
  },
  {
    re: /^验证未通过（未通过：(.+)）。只能导出研究记录包。$/,
    render: (m, t) => t("ui.copy.hintFailed", {gates: gates(m[1], t)}),
  },
  {
    re: /^冻结验证已通过，策略包门禁未满足：(.+)。$/,
    render: (m, t) => t("ui.copy.hintHandoff", {gates: gates(m[1], t)}),
  },
  {
    re: /^第 (\d+)\/(\d+) 轮验证未通过（未通过：(.+)）。系统仅在实现层调整参数，不改经济逻辑，阈值不变，自动迭代中。(?: (本窗口所有研究累计 (\d+) 轮)。)?$/,
    render: (m, t) => {
      const base = t("ui.copy.hintRunning", {used: m[1], budget: m[2], gates: gates(m[3], t)});
      if (!m[5]) return base;
      return t("ui.copy.hintRunningWindow", {
        base,
        window: t("ui.completed.iterateFallback", {n: m[5]}),
      });
    },
  },
  {
    re: /^本窗口所有研究累计 (\d+) 轮$/,
    render: (m, t) => t("ui.completed.iterateFallback", {n: m[1]}),
  },
  {
    re: /^本研究在本窗口累计 (\d+) 轮$/,
    render: (m, t) => t("ui.copy.researchThisWindow", {n: m[1]}),
  },
  {
    re: /^本版本 (\d+)\/(\d+) 轮$/,
    render: (m, t) => t("ui.copy.versionTrials", {used: m[1], budget: m[2]}),
  },
  {
    re: /^「(.+)」重验通过。$/,
    render: (m, t) => t("ui.copy.reverifyPass", {method: exactLabel(m[1], t)}),
  },
  {
    re: /^「(.+)」重验未通过。$/,
    render: (m, t) => t("ui.copy.reverifyFail", {method: exactLabel(m[1], t)}),
  },
  {
    re: /^仅「(.+)」重验通过；整轮结论未变。仍未通过：(.+)。$/,
    render: (m, t) => t("ui.copy.reverifyUnchanged", {method: exactLabel(m[1], t), gates: gates(m[2], t)}),
  },
  {
    re: /^(.+)，暂不能导出策略包$/,
    render: (m, t) => t("ui.copy.blockGate", {gate: gateToken(m[1], t)}),
  },
  {
    re: /^模型变更：(.+)$/,
    render: (m, t) => t("ui.running.modelChanges", {
      changes: m[1].split("、").map((part) => paramPiece(part, t)).join(t("ui.copy.gateJoiner")),
    }),
  },
  {
    re: /^变更：(.+)$/,
    render: (m, t) => t("ui.copy.changeLine", {text: m[1]}),
  },
  {
    re: /^当前 (\d+) 个标的、([\d.]+) 年数据，缺失 ([\d.]+)%；底线 (.+)$/,
    render: (m, t) => t("ui.copy.coverageWithFloor", {
      current: coverageSentence("now", m[1], m[2], m[3], t),
      floor: localizeKnownCopy(m[4], t),
    }),
  },
  {
    re: /^当前 (\d+) 个标的、([\d.]+) 年数据，缺失 ([\d.]+)%$/,
    render: (m, t) => coverageSentence("now", m[1], m[2], m[3], t),
  },
  {
    re: /^至少 (\d+) 个标的、([\d.]+) 年数据，缺失不超过 ([\d.]+)%$/,
    render: (m, t) => coverageSentence("floor", m[1], m[2], m[3], t),
  },
  {
    re: /^至少 (\d+) 个标的、([\d.]+) 年、缺失不超过 ([\d.]+)%$/,
    render: (m, t) => coverageSentence("floor", m[1], m[2], m[3], t),
  },
  {
    re: /^至少 (\d+) 个标的$/,
    render: (m, t) => t("ui.copy.coverageFloorShort", {assets: m[1]}),
  },
  {
    re: /^(美股|A股) · (股票|债券|基金)(?:（(.+)）)?$/,
    render: (m, t) => {
      const line = t("ui.copy.universe", {
        market: t(m[1] === "美股" ? "ui.copy.marketUs" : "ui.copy.marketCn"),
        asset: t(m[2] === "股票" ? "ui.copy.assetEquity" : m[2] === "债券" ? "ui.copy.assetBond" : "ui.copy.assetFund"),
      });
      return m[3] ? t("ui.copy.universeSymbols", {line, symbols: m[3]}) : line;
    },
  },
  {
    re: /^已开始第 (\d+) 版。$/,
    render: (m, t) => t("ui.copy.versionOpened", {version: m[1]}),
  },
  {
    re: /^第 (\d+) 轮$/,
    render: (m, t) => t("ui.completed.roundN", {n: m[1]}),
  },
  {
    re: /^(.+?) · 内置第 (\d+) 版$/,
    render: (m, t) => t("ui.copy.revisionBuiltin", {name: exactLabel(m[1], t), n: m[2]}),
  },
];

/**
 * Translate a known engine product sentence. Unrecognized text, including
 * user theses and literature titles, is returned unchanged.
 */
export function localizeKnownCopy(text: string, t: CopyFn): string {
  const duration = formatEngineDuration(text, t);
  if (duration != null) return duration;
  const exact = EXACT[text];
  if (exact) return t(exact);
  const shrunk = SHRINK.exec(text);
  if (shrunk) {
    const shrink = t("ui.copy.shrink", {dropped: shrunk[1], remaining: shrunk[2]});
    if (!shrunk[3]) return shrink;
    return `${shrink} ${localizeKnownCopy(shrunk[3], t)}`;
  }
  for (const rule of RULES) {
    const match = rule.re.exec(text);
    if (match) return rule.render(match, t);
  }
  const parts = text.split(" · ");
  if (parts.length > 1 && parts.every((part) => LABELS.some(([zh]) => zh === part))) {
    return parts.map((part) => exactLabel(part, t)).join(" · ");
  }
  return gateToken(text, t);
}
