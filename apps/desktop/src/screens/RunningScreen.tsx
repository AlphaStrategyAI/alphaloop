import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";
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
  const quota = parseEffectiveQuotaFromView(view.effective, view.remaining);
  const stageLabel =
    view.currentAction && view.currentAction !== "idle" ? view.currentAction : null;
  return (
    <div
      className={`focus running-screen${runStartRitual ? " run-start-ritual-running" : ""}`}
      data-testid="running-screen"
      data-run-start-ritual={runStartRitual ? "active" : undefined}
    >
      <div className="running-hero">
        <div className="version-orbit" data-testid="version-orbit">
          <span className="orbit-version">v{view.version}</span>
          {stageLabel ? <span className="orbit-stage">{stageLabel}</span> : null}
        </div>
        <div>
          <h1>{t("ui.running.title")}</h1>
          <p className="running-sub">
            {t("ui.running.version", {version: view.version})}
            {view.currentAction && view.currentAction !== "idle" ? ` · ${view.currentAction}` : ""}
          </p>
          {view.coverage && <p className="running-accent">{view.coverage}</p>}
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
            <span>{quota.usedLabel} / {quota.totalLabel}</span>
          </div>
          <div
            className="effective-quota-track"
            data-testid="effective-quota-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(quota.ratio * 100)}
          >
            <div className="effective-quota-fill" style={{width: `${quota.ratio * 100}%`}} />
          </div>
        </div>
      )}
      {view.versionOpenedNotice && (
        <p className="version-opened-banner" data-testid="version-opened-banner" role="status">
          {view.versionOpenedNotice}
        </p>
      )}
      <header className="running-header">
        <StatusPill status={view.status} />
        {view.currentAction && view.currentAction !== "idle"
          ? ` ${view.currentAction} · `
          : " "}
        {t("ui.running.header", {version: view.version, effective: view.effective})}
        {view.remaining ? ` · ${t("ui.running.remaining", {remaining: view.remaining})}` : ""}
        {" · "}{view.coverage}
        {view.workbenchHeaderSummary ? ` · ${view.workbenchHeaderSummary}` : ""}
        {view.versionTrialLabel ? ` · ${view.versionTrialLabel}` : ""}
        {!view.workbenchHeaderSummary && view.windowCumulativeLabel
          ? ` · ${view.windowCumulativeLabel}`
          : ""}
      </header>
      {view.effectiveTimeHint && (
        <p className="effective-time-hint" data-testid="effective-time-hint">
          {view.effectiveTimeHint}
        </p>
      )}
      {view.lastError && <LocalizedRunError error={view.lastError} />}
      {view.honestStopHint && (
        <p className="honest-stop-hint" data-testid="honest-stop-hint-running">
          {view.honestStopHint}
        </p>
      )}
      <section className="materials-note">
        <p className="eyebrow">{t("ui.running.materials")}</p>
        <p>{t("ui.running.sources", {sources: view.sources ?? t("ui.running.sourcesFallback")})}</p>
        <p>{t("ui.running.cutoff", {cutoff: view.dataCutoff || t("ui.running.cutoffFallback")})}</p>
        <p>{t("ui.running.coverageNow", {coverage: view.coverage})}</p>
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
              <p>{round.logicStatement.statement}</p>
            </div>
            <div className="round-impl">
              <p className="eyebrow">{t("ui.running.implementation")}</p>
              {round.implementationDelta.modelChangesDisplay ? (
                <p>{round.implementationDelta.modelChangesDisplay}</p>
              ) : (
                round.implementationDelta.modelChanges.length > 0 && (
                  <p>{t("ui.running.modelChanges", {changes: round.implementationDelta.modelChanges.join("、")})}</p>
                )
              )}
              {round.logicStatement.changedFromPrior && round.logicStatement.changeDescription && (
                <p className="change-note">{round.logicStatement.changeDescription}</p>
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
          <button className="quiet-button" onClick={() => void api.resumeResearch(view.researchId)}>{t("ui.running.resume")}</button>
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
  );
}

