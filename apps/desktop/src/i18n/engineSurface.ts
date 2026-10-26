import type {MessageKey} from "./I18nProvider";
import type {CopyFn} from "./productCopy";

/** Chinese fragments the engine still emits. English replaces them; Chinese stays. */
const FRAGMENTS: ReadonlyArray<readonly [string, MessageKey]> = [
  ["检验样本外各段收益方向是否同号。这和「分段稳健性检验」不是同一项：后者看时间分段上前缀与下一段是否一致，这一项只看方向是否稳定。", "ui.surface.stabilityPurpose"],
  ["按时间把固定参数的收益切成若干段，比较前缀与下一段的表现是否一致。这是时间分段表现一致性，不是重新估计参数的 walk-forward。", "ui.surface.walkPurpose"],
  ["用持仓绝对权重的高分位估计对夏普的影响。这是权重集中度（非市场拥挤度）。", "ui.surface.crowdingPurpose"],
  ["确保证据与回测只使用决策当时可获得的信息，杜绝前视偏差。", "ui.surface.pitPurpose"],
  ["证据与回测窗口仅使用决策当时可获得的信息。", "ui.surface.pitExplain"],
  ["用多维指标衡量策略是否达到最低可接受表现。", "ui.surface.scorecardPurpose"],
  ["在换手成本下检验净超额是否仍为正。", "ui.surface.costPurpose"],
  ["检测到前视偏差（详见违规项）", "ui.surface.pitLookahead"],
  ["样本外表现与样本内的比值下限", "ui.surface.ratioDesc"],
  ["样本外分段收益方向一致的比例下限", "ui.surface.signDesc"],
  ["样本外分段数量下限", "ui.surface.segmentDesc"],
  ["样本外夏普下限（不含等于）", "ui.surface.sharpeFloor"],
  ["年化超额下限（不含等于）", "ui.surface.excessFloor"],
  ["净超额下限（不含等于）", "ui.surface.netExcessFloor"],
  ["样本外夏普比率下限", "ui.surface.sharpeDesc"],
  ["样本外/样本内比下限", "ui.surface.oosToIs"],
  ["夏普影响下限", "ui.surface.sharpeImpactFloor"],
  ["同号比例下限", "ui.surface.sameSignFloor"],
  ["分段数下限", "ui.surface.segmentsFloor"],
  ["最大回撤下限", "ui.surface.drawdownFloor"],
  ["美股成本（bp）", "ui.surface.usCost"],
  ["A 股成本（bp）", "ui.surface.cnCost"],
  ["头部桶占比（%）", "ui.surface.topBucket"],
  ["检查是否存在前视偏差", "ui.surface.pitCheck"],
  ["夏普不高于基准", "ui.surface.sharpeFail"],
  ["样本外方向不稳定", "ui.surface.signFail"],
  ["分段表现未保持", "ui.surface.ratioFail"],
  ["样本外分段不足", "ui.surface.segmentFail"],
  ["冻结验证方法定义。", "ui.surface.frozenPurpose"],
  ["样本外/样本内比", "ui.surface.ratioName"],
  ["时点一致性", "ui.surface.pitKind"],
  ["成本敏感度", "ui.surface.costKind"],
  ["过拟合检测", "ui.surface.overfitCategory"],
  ["存在前视偏差", "ui.surface.pitFail"],
  ["最大回撤", "ui.surface.drawdownName"],
  ["回撤上限", "ui.surface.drawdownDesc"],
  ["回撤过大", "ui.surface.drawdownFail"],
  ["夏普比率", "ui.surface.sharpeName"],
  ["同号比例", "ui.surface.signName"],
  ["分段折数", "ui.surface.nSplits"],
  ["分段数", "ui.surface.segmentName"],
  ["检查范围", "ui.surface.scope"],
  ["预测力", "ui.surface.predictive"],
  ["稳定性", "ui.surface.stabilityKind"],
  ["集中度", "ui.surface.crowdingKind"],
  ["计分卡", "ui.surface.scorecardCategory"],
  ["自定义", "ui.surface.customKind"],
  ["未通过提示：", "ui.surface.failureHint"],
  ["通过阈值：", "ui.surface.threshold"],
  ["比较方式：", "ui.surface.comparison"],
  ["（无正文）", "ui.surface.noBody"],
  ["用途：", "ui.surface.purpose"],
  ["维度：", "ui.surface.dimension"],
  ["说明：", "ui.surface.explanation"],
  ["类别：", "ui.surface.category"],
  ["类别", "ui.surface.category"],
  ["单位：", "ui.surface.unit"],
  ["净超额不为正", "ui.surface.netExcessFail"],
  ["净超额", "ui.surface.netExcess"],
  ["成本", "ui.surface.costCategory"],
  ["不小于", "ui.surface.cmpGte"],
  ["不大于", "ui.surface.cmpLte"],
  ["大于", "ui.surface.cmpGt"],
  ["小于", "ui.surface.cmpLt"],
  ["等于", "ui.surface.cmpEq"],
  ["是", "ui.surface.yes"],
  ["否", "ui.surface.no"],
];

const ORDERED = [...FRAGMENTS].sort((left, right) => right[0].length - left[0].length);

/** Replace known engine Chinese in an English surface. Chinese UI keeps the source text. */
export function localizeEngineSurface(text: string, t: CopyFn, locale: "zh" | "en"): string {
  if (!text || locale !== "en") return text;
  let out = text;
  for (const [zh, key] of ORDERED) {
    if (out.includes(zh)) out = out.split(zh).join(t(key));
  }
  return out;
}
