import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {LogicStatementText} from "../i18n/logicStatement";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import {localizeKnownCopy} from "../i18n/productCopy";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {formatDuration, formatEngineDuration} from "../duration";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";
import {missingSymbolsError} from "../missingSymbols";
import {DetailFrame} from "./DetailFrame";
import {StatusPill} from "./ResearchListScreen";

export function RunningScreen({
  api,
  view,
  modification,
  onModificationChange,
  runStartRitual,
}: {
  api: DesktopApi;
  view: Extract<DesktopView, {kind: "running"}>;
  modification: string;
  onModificationChange: (text: string) => void;
  runStartRitual?: boolean;
}) {
  const {t} = useI18n();
  const [tickerOpen, setTickerOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const paused = view.status === "paused";
  const statusKey = paused ? "ui.status.paused" : "ui.status.running";
  const needsTickers = missingSymbolsError(view.lastError);
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const parsedQuota = parseEffectiveQuotaFromView(view.effective, view.remaining);
  const quota = view.effectiveSeconds != null && view.remainingSeconds != null
    && view.effectiveSeconds + view.remainingSeconds > 0
    ? {
        usedLabel: formatDuration(view.effectiveSeconds, t),
        totalLabel: formatDuration(view.remainingSeconds + view.effectiveSeconds, t),
        ratio: Math.min(1, Math.max(0, view.effectiveSeconds / (view.effectiveSeconds + view.remainingSeconds))),
      }
    : parsedQuota;
  const effectiveLabel = view.effectiveSeconds != null
    ? formatDuration(view.effectiveSeconds, t)
    : copyText(view.effective);
  const stageLabel =
    view.currentAction && view.currentAction !== "idle" ? copyText(view.currentAction) : null;
  const tickerForm = tickerOpen ? (
    <form
      className="ticker-set-form"
      onSubmit={(event) => {
        event.preventDefault();
        const next = symbol.trim();
        if (!next) return;
        void api.setResearchSymbol(view.researchId, next);
      }}
    >
      <label>
        {t("ui.confirm.symbolEdit")}
        <input
          data-testid="paused-symbol-input"
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
        />
      </label>
    </form>
  ) : null;
  const setTickers = (
    <div className="missing-ticker-actions">
      <button
        type="button"
        className="hold-button"
        data-testid="go-set-tickers"
        onClick={() => setTickerOpen(true)}
      >
        {t("ui.running.setTickers")}
      </button>
      {tickerForm}
    </div>
  );
  return (
    <DetailFrame
      aside={
        <>
          <h2>{t("ui.running.asideTitle")}</h2>
          <p className="eyebrow">{t("ui.running.symbolsLabel")}</p>
          <p data-testid="aside-symbols" className={needsTickers ? "is-unset" : undefined}>
            {needsTickers ? t("ui.running.symbolsUnset") : copyText(view.coverage)}
          </p>
          {needsTickers ? (
            <button type="button" className="hold-button" onClick={() => setTickerOpen(true)}>
              {t("ui.running.setTickers")}
            </button>
          ) : null}
          <p className="eyebrow">{t("ui.brief.coverage")}</p>
          <p>{copyText(view.coverage)}</p>
        </>
      }
    >
    <div
      className={`focus running-screen${runStartRitual ? " run-start-ritual-running" : ""}`}
      data-testid="running-screen"
      data-status={view.status}
      data-run-start-ritual={runStartRitual ? "active" : undefined}
    >
      <div className="running-hero">
        <div
          className={`version-orbit phase-ring${paused ? " version-orbit--paused" : ""}`}
          data-testid="version-orbit"
          data-phase-ring={paused ? "static" : "rotate"}
          data-phase-rotate={paused ? undefined : "1.2s"}
          data-run-enter={runStartRitual ? "280" : undefined}
        >
          {paused ? null : <span className="phase-ring-arc" data-testid="phase-ring-arc" aria-hidden="true" />}
          <span className="orbit-version">v{view.version}</span>
          {stageLabel ? <span className="orbit-stage">{stageLabel}</span> : null}
        </div>
        <div>
          <h1 className="run-status-title" data-testid="run-status-title" data-status={view.status}>{t(statusKey)}</h1>
          <p className="running-sub">
            {t("ui.running.version", {version: view.version})}
            {view.currentAction && view.currentAction !== "idle" ? ` · ${copyText(view.currentAction)}` : ""}
          </p>
          {view.coverage && <p className="running-accent">{copyText(view.coverage)}</p>}
        </div>
        {view.status === "running" ? (
          <button className="quiet-button" type="button" onClick={() => void api.pauseResearch(view.researchId)}>
            {t("ui.running.pause")}
          </button>
        ) : (
          <span />
        )}
      </div>
      {quota && (
        <div className="effective-quota" data-testid="effective-quota-progress">
          <div className="effective-quota-labels">
            <span>{t("ui.running.quota")}</span>
            <span>{formatEngineDuration(quota.usedLabel, t) ?? quota.usedLabel} / {formatEngineDuration(quota.totalLabel, t) ?? quota.totalLabel}</span>
          </div>
          <div
            className="effective-quota-track"
            data-testid="effective-quota-track"
            data-track-px="8"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(quota.ratio * 100)}
          >
            <div
              className={`effective-quota-fill${paused ? "" : " quota-sheen"}`}
              data-testid="effective-quota-fill"
              data-sheen={paused ? undefined : "1.6s"}
              style={{width: `${quota.ratio * 100}%`}}
            />
          </div>
        </div>
      )}
      {view.versionOpenedNotice && (
        <p className="version-opened-banner" data-testid="version-opened-banner" role="status">
          {copyText(view.versionOpenedNotice)}
        </p>
      )}
      <header className="running-header">
        <StatusPill status={view.status} />
        {view.currentAction && view.currentAction !== "idle"
          ? ` ${copyText(view.currentAction)} · `
          : " "}
        {t("ui.running.header", {version: view.version, effective: effectiveLabel})}
        {view.remaining ? ` · ${t("ui.running.remaining", {remaining: copyText(view.remaining)})}` : ""}
        {" · "}{copyText(view.coverage)}
        {view.workbenchHeaderSummary ? ` · ${copyText(view.workbenchHeaderSummary)}` : ""}
        {view.versionTrialLabel ? ` · ${copyText(view.versionTrialLabel)}` : ""}
        {!view.workbenchHeaderSummary && view.windowCumulativeLabel
          ? ` · ${copyText(view.windowCumulativeLabel)}`
          : ""}
      </header>
      {view.effectiveTimeHint && (
        <p className="effective-time-hint" data-testid="effective-time-hint">
          {copyText(view.effectiveTimeHint)}
        </p>
      )}
      {view.lastError && needsTickers ? (
        <div className="missing-ticker-warning" data-testid="missing-ticker-warning">
          <LocalizedRunError error={view.lastError} />
          <p>{t("ui.running.setTickersHint")}</p>
          {setTickers}
        </div>
      ) : view.lastError ? (
        <LocalizedRunError error={view.lastError} />
      ) : null}
      {view.honestStopHint && (
        <p className="honest-stop-hint" data-testid="honest-stop-hint-running">
          {copyText(view.honestStopHint)}
        </p>
      )}
      <section className="materials-note">
        <p className="eyebrow">{t("ui.running.materials")}</p>
        <p>{t("ui.running.sources", {sources: copyText(view.sources) || t("ui.running.sourcesFallback")})}</p>
        <p>{t("ui.running.cutoff", {cutoff: view.dataCutoff || t("ui.running.cutoffFallback")})}</p>
        <p>{t("ui.running.coverageNow", {coverage: copyText(view.coverage)})}</p>
        <p>{t("ui.running.notATerminal")}</p>
      </section>
      <h1>{t("ui.running.roundsTitle")}</h1>
      {view.anomaly && <AnomalyChecklist anomaly={view.anomaly} />}
      {view.rounds.map((round, index) => (
        <article className="round-card" key={round.roundId} data-testid="round-card">
          <small>{t("ui.running.roundLabel", {version: view.version, n: view.rounds.length - index})}</small>
          <div className="round-columns">
            <div className="round-logic">
              <p className="eyebrow">{t("ui.running.logic")}</p>
              <p data-testid="logic-statement"><LogicStatementText text={round.logicStatement.statement} /></p>
            </div>
            <div className="round-impl">
              <p className="eyebrow">{t("ui.running.implementation")}</p>
              {round.implementationDelta.modelChangesDisplay ? (
                <p>{copyText(round.implementationDelta.modelChangesDisplay)}</p>
              ) : (
                round.implementationDelta.modelChanges.length > 0 && (
                  <p>{t("ui.running.modelChanges", {changes: round.implementationDelta.modelChanges.join("、")})}</p>
                )
              )}
              {round.logicStatement.changedFromPrior && round.logicStatement.changeDescription && (
                <p className="change-note">{copyText(round.logicStatement.changeDescription)}</p>
              )}
              {round.implementationDelta.paramChanges.length > 0 && (
                <ul className="param-changes">
                  {round.implementationDelta.paramChanges.map(([param, from, to]) => (
                    <li key={param}>{param}: {from} → {to}</li>
                  ))}
                </ul>
              )}
              {round.implementationDelta.modelChanges.length === 0 &&
               round.implementationDelta.paramChanges.length === 0 && (
                <p className="no-changes">{t("ui.running.noChanges")}</p>
              )}
            </div>
          </div>
          <div className="trial-counters">
            <span>{t("ui.running.candidates", {n: round.trialCounters.candidatesEvaluated})}</span>
            <span>{t("ui.running.passed", {n: round.trialCounters.candidatesPassed})}</span>
            <span>{t("ui.running.attempt", {n: round.trialCounters.conclusionAttemptNumber})}</span>
            <span className={round.verificationPassed ? "passed" : "failed"}>
              {round.verificationPassed ? t("ui.running.verificationPassed") : t("ui.running.verificationFailed")}
            </span>
          </div>
        </article>
      ))}
      {view.status === "running" && (
        <p className="running-modify-hint" data-testid="running-modify-hint">
          {t("ui.running.cannotEdit")}
        </p>
      )}
      {view.status === "running" ? null : (
        <>
          <button className="cyan-button" onClick={() => void api.resumeResearch(view.researchId)}>{t("ui.running.resume")}</button>
          <input
            value={modification}
            onChange={(event) => onModificationChange(event.target.value)}
            placeholder={t("ui.running.modifyPlaceholder")}
            data-testid="paused-modification-input"
          />
          <button
            className="quiet-button"
            data-testid="confirm-modification-button"
            disabled={!modification.trim()}
            onClick={() => void (async () => {
              await api.sendDialogue(view.researchId, modification.trim());
              await api.confirmModification(view.researchId);
            })()}
          >
            {t("ui.running.confirmModification")}
          </button>
        </>
      )}
    </div>
    </DetailFrame>
  );
}

