import type {ReactNode} from "react";
import type {AnomalyPresentation} from "../contracts";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import type {MessageParams} from "../i18n/translate";

export type Translate = (key: MessageKey, params?: MessageParams) => string;

const CN_TICKER_IN_PROSE = /(\d{6}\.(?:SH|SZ|BJ))/g;

export function renderSettingsProse(text: string) {
  const parts: Array<string | {token: string; key: string}> = [];
  let last = 0;
  for (const match of text.matchAll(CN_TICKER_IN_PROSE)) {
    const index = match.index ?? 0;
    if (index > last) {
      parts.push(text.slice(last, index));
    }
    parts.push({token: match[1], key: `${index}-${match[1]}`});
    last = index + match[1].length;
  }
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  if (parts.length === 0) {
    return text;
  }
  return parts.map((part) =>
    typeof part === "string" ? (
      part
    ) : (
      <span className="cn-ticker-nowrap" key={part.key}>{part.token}</span>
    ),
  );
}


export function AnomalyChecklist({anomaly}: {anomaly: AnomalyPresentation}) {
  const {t} = useI18n();
  const anomalyIndicatorLabels: Record<string, string> = {
    sharpe_outlier: t("ui.anomaly.sharpeOutlier"),
    coverage_shrunk: t("ui.anomaly.coverageShrunk"),
    high_trial_count: t("ui.anomaly.highTrialCount"),
    recent_method_revision: t("ui.anomaly.recentRevision"),
  };
  const baseline = anomaly.baseline;
  const hasSharpe = baseline && "sharpe" in baseline && baseline.sharpe != null;
  const hasTrialCount = baseline && "trialCount" in baseline && baseline.trialCount != null;
  return (
    <section className="anomaly-section" data-testid="anomaly-checklist">
      <h4>{t("ui.anomaly.title")}</h4>
      {baseline && (
        <p className="baseline-note">
          {t("ui.anomaly.baseline", {kind: baseline.kind === "version_1_logic" ? t("ui.anomaly.version1") : baseline.kind})}
          {hasSharpe && ` · ${t("ui.anomaly.sharpe", {value: (baseline as {sharpe: number}).sharpe})}`}
          {hasTrialCount && ` · ${t("ui.anomaly.trials", {value: (baseline as {trialCount: number}).trialCount})}`}
        </p>
      )}
      <ul className="anomaly-checklist">
        {anomaly.indicators.map((indicator) => (
          <li key={indicator}>
            <span className="indicator-icon">⚠</span>
            <span>{anomalyIndicatorLabels[indicator] ?? indicator}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

