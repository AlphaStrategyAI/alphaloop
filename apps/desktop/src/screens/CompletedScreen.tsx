import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {EngineFailureText} from "../i18n/engineFailure";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {I18nText} from "../i18n/I18nText";
import {LogicStatementText} from "../i18n/logicStatement";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import {localizeKnownCopy} from "../i18n/productCopy";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {formatDuration} from "../duration";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";

function ExportOutcomeMessages({
  exportFeedback,
  openFolderError,
  onReveal,
}: {
  exportFeedback: {status: "success"; path: string} | {status: "error"; message: string} | null;
  openFolderError: string | null;
  onReveal: (path: string) => void;
}) {
  const {t} = useI18n();
  return (
    <div className="export-outcome-messages" data-testid="export-outcome-messages">
      {exportFeedback?.status === "success" && (
        <p className="export-feedback success" data-testid="export-success" role="status">
          {t("ui.export.exported", {path: exportFeedback.path})}
          <button
            type="button"
            className="text-button"
            data-testid="reveal-export-folder"
            onClick={() => onReveal(exportFeedback.path)}
          >
            {t("ui.export.reveal")}
          </button>
        </p>
      )}
      {exportFeedback?.status === "error" && (
        <div className="export-feedback error" data-testid="export-error" role="alert">
          {t("ui.export.failed", {message: ""})}
          <EngineFailureText raw={exportFeedback.message} />
        </div>
      )}
      {openFolderError && (
        <p className="export-feedback error" data-testid="open-folder-error" role="alert">
          {openFolderError}
        </p>
      )}
    </div>
  );
}

function ExportFeedbackBlock({
  exportFeedback,
  openFolderError,
  onExport,
  onReveal,
}: {
  exportFeedback: {status: "success"; path: string} | {status: "error"; message: string} | null;
  openFolderError: string | null;
  onExport: () => void;
  onReveal: (path: string) => void;
}) {
  const {t} = useI18n();
  return (
    <div className="export-actions" data-testid="export-research-record-block">
      <button
        type="button"
        className="cyan-button"
        data-testid="export-research-record"
        onClick={onExport}
      >
        {t("ui.export.researchRecord")}
      </button>
      {exportFeedback?.status === "success" && (
        <p className="export-feedback success" data-testid="export-success" role="status">
          {t("ui.export.exported", {path: exportFeedback.path})}
          <button
            type="button"
            className="text-button"
            data-testid="reveal-export-folder"
            onClick={() => onReveal(exportFeedback.path)}
          >
            {t("ui.export.reveal")}
          </button>
        </p>
      )}
      {exportFeedback?.status === "error" && (
        <div className="export-feedback error" data-testid="export-error" role="alert">
          {t("ui.export.failed", {message: ""})}
          <EngineFailureText raw={exportFeedback.message} />
        </div>
      )}
      {openFolderError && (
        <p className="export-feedback error" data-testid="open-folder-error" role="alert">
          {openFolderError}
        </p>
      )}
    </div>
  );
}

function pitGateLabel(detail: PitDetail | null | undefined, passed: boolean, t: Translate): string {
  if (passed) return t("ui.pit.passed");
  if (!detail || detail.executed === false) return t("ui.pit.notRun");
  return t("ui.pit.failed");
}

function PitFailureText({text, title}: {text: string; title?: string | null}) {
  if (!title) return text;
  const index = text.indexOf(title);
  if (index < 0) return text;
  return (
    <>
      {text.slice(0, index)}
      <span data-user-content="true">{title}</span>
      {text.slice(index + title.length)}
    </>
  );
}

function pitFailureCopy(detail: PitDetail | null | undefined, t: Translate): string | null {
  if (!detail || detail.passed) return null;
  if (detail.executed === false) {
    return t("ui.pit.notRunBlocks");
  }
  const count = detail.violationCount ?? 0;
  const first = detail.firstViolation;
  if (!first) {
    return t("ui.pit.failedBlocks");
  }
  const doi = first.materialId.startsWith("doi:") ? first.materialId.slice(4) : "";
  const title = first.title || first.text || first.materialId || t("ui.pit.unnamed");
  const yearNote = first.precision === "year" ? t("ui.pit.yearNote") : "";
  const when = first.publishedAt
    ? t("ui.pit.published", {date: first.publishedAt, yearNote})
    : t("ui.pit.noPublished");
  const cutoff = detail.backtestCutoff ? t("ui.pit.cutoff", {date: detail.backtestCutoff}) : t("ui.pit.noCutoff");
  const doiPart = doi ? t("ui.pit.doiPart", {doi}) : "";
  return t(count === 1 ? "ui.pit.firstViolationOne" : "ui.pit.firstViolation", {
    count,
    title,
    doiPart,
    when,
    cutoff,
  });
}

export function CompletedScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "completed"}>}) {
  const {t} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const [extensionHours, setExtensionHours] = useState("4");
  const [modification, setModification] = useState("");
  const [iterateConfirm, setIterateConfirm] = useState<InAppConfirmRequest | null>(null);
  const [reverifyRoundId, setReverifyRoundId] = useState(view.selectedRoundId);
  const [reverifyMethodId, setReverifyMethodId] = useState(view.selectedMethodId);
  const [reverifyBusy, setReverifyBusy] = useState(false);
  const [reverifyError, setReverifyError] = useState<string | null>(null);
  const [exportFeedback, setExportFeedback] = useState<
    {status: "success"; path: string} | {status: "error"; message: string} | null
  >(null);
  const [openFolderError, setOpenFolderError] = useState<string | null>(null);

  useEffect(() => {
    setReverifyRoundId(view.selectedRoundId);
    setReverifyMethodId(view.selectedMethodId);
  }, [view.selectedRoundId, view.selectedMethodId]);

  const runExport = async (kind: "strategy_pack" | "research_record") => {
    setExportFeedback(null);
    setOpenFolderError(null);
    try {
      const path = await api.exportArtifact(view.researchId, kind);
      setExportFeedback({status: "success", path});
    } catch (error) {
      setExportFeedback({
        status: "error",
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };
  const revealExportFolder = (path: string) => {
    void api.revealExportInFolder(path).catch(async () => {
      setOpenFolderError(t("ui.export.folderFailed", {path}));
      try {
        await navigator.clipboard.writeText(path);
      } catch {
        /* clipboard unavailable */
      }
    });
  };
  const pitLabel = pitGateLabel(view.pitDetail, view.eligibility.pitExecutedAndPassed, t);
  const checks = [
    [t("ui.completed.gateMethods"), view.eligibility.allMethodsPassed],
    [t("ui.completed.gatePending"), view.eligibility.noPendingConfirm],
    [t("ui.completed.gateReverify"), view.eligibility.reverifiesPassed],
    [pitLabel, view.eligibility.pitExecutedAndPassed],
  ] as const;
  const pitFailure = pitFailureCopy(view.pitDetail, t);
  const eligible = checks.every(([, passed]) => passed);
  const researchRecordExportPrimary = completedShowsFailedTone(view);
  const headline = view.resultHeadline
    ? copyText(view.resultHeadline)
    : (eligible ? t("ui.completed.doneOk") : t("ui.completed.doneFailed"));
  // The engine sentence still uses this phrase. Match the raw subtitle.
  const gatesInSubtitle = Boolean(view.subtitle?.includes("未通过门禁")); // i18n-allow engine copy
  const showFailedGateLine =
    view.failedVerifierIds &&
    view.failedVerifierIds.length > 0 &&
    !gatesInSubtitle;
  const reverifyRounds = view.reverifyOptions?.rounds ?? [];
  const methodsForRound =
    reverifyRounds.find((item) => item.roundId === reverifyRoundId)?.methods ?? [];
  const runReverify = async () => {
    if (!reverifyRoundId || !reverifyMethodId) {
      setReverifyError(t("ui.completed.pickRound"));
      return;
    }
    setReverifyBusy(true);
    setReverifyError(null);
    try {
      await api.reverify(view.researchId, reverifyRoundId, reverifyMethodId);
    } catch (error) {
      setReverifyError(error instanceof Error ? error.message : String(error));
    } finally {
      setReverifyBusy(false);
    }
  };

  return (
    <div
      className={`focus completed-screen${researchRecordExportPrimary ? " tech-pulse-failed-tone" : " tech-pulse-success-tone"}`}
      data-testid="completed-screen"
    >
      <InAppConfirmOverlay request={iterateConfirm} onClose={() => setIterateConfirm(null)} />
      <article
        className={`completed-focus-card tech-pulse-card${eligible ? " completed-focus-card--success" : " completed-focus-card--failed"}`}
        data-testid="completed-focus-card"
      >
        {eligible ? (
          <p className="export-ready-eyebrow" data-testid="export-ready-eyebrow">
            {t("ui.completed.readyEyebrow")}
          </p>
        ) : (
          <p className="failed-eyebrow" data-testid="completed-failed-eyebrow">
            {t("ui.completed.failedEyebrow")}
          </p>
        )}
        <h1 data-testid="completed-focus-title">{eligible ? t("ui.completed.title") : t("ui.completed.title")}</h1>
        <p className="completed-focus-headline">{headline}</p>
        {view.meanReversionOnlyNotice && (
          <p className="confirm-lead" data-testid="mean-reversion-only-notice">
            {copyText(view.meanReversionOnlyNotice)}
          </p>
        )}
        {view.cnExecutionNotice && (
          <p className="confirm-lead" data-testid="cn-execution-notice">
            {copyText(view.cnExecutionNotice)}
          </p>
        )}
        {view.subtitle && <p className="completed-focus-subtitle">{copyText(view.subtitle)}</p>}
        {view.honestStopHint && (
          <p className="honest-stop-hint" data-testid="honest-stop-hint">{copyText(view.honestStopHint)}</p>
        )}
        {view.stopReason === "round_cap" && (
          <p className="honest-stop-hint" data-testid="stop-reason">
            {t("ui.copy.stopRoundCap", {
              used: view.trialBudget?.used ?? 0,
              budget: view.trialBudget?.budget ?? 0,
            })}
          </p>
        )}
        {view.stopReason === "time_budget" && (
          <p className="honest-stop-hint" data-testid="stop-reason">{t("ui.copy.stopTimeBudget")}</p>
        )}
        {view.stopReason === "early_stop" && (
          <p className="honest-stop-hint" data-testid="stop-reason">{t("ui.copy.stopEarly")}</p>
        )}
        <div className="eligibility eligibility-pills" data-testid="completed-gate-pills">
          {checks.map(([label, passed]) => (
            <span className={`gate-pill ${passed ? "gate-pill--ok" : "gate-pill--fail"}`} key={label}>
              {passed ? "●" : "○"} {label}
            </span>
          ))}
        </div>
        {view.pitDetail && (view.pitDetail.scope || view.pitDetail.note || pitFailure) && (
          <p className="materials-note" data-testid="pit-detail">
            {pitFailure ? (
              <span data-testid="pit-failure-reason">
                <PitFailureText text={pitFailure} title={view.pitDetail?.firstViolation?.title} />
              </span>
            ) : null}
            {view.pitDetail.note ? `${copyText(view.pitDetail.note)}${t("ui.pit.sentenceStop")}` : ""}
            {view.pitDetail.executed ? (
              <>
                {t((view.pitDetail.evidenceUsed ?? 0) === 1 ? "ui.pit.trustedOne" : "ui.pit.trusted", {
                  count: view.pitDetail.evidenceUsed ?? 0,
                })}
                {(view.pitDetail.undatedExcluded?.length ?? 0) > 0
                  ? t((view.pitDetail.undatedExcluded?.length ?? 0) === 1 ? "ui.pit.undatedOne" : "ui.pit.undated", {
                      count: view.pitDetail.undatedExcluded?.length ?? 0,
                    })
                  : ""}
                {t("ui.pit.sentenceStop")}{copyText(view.pitDetail.scope)}
              </>
            ) : null}
          </p>
        )}
        {view.sources && (
          <p className="materials-note" data-testid="completed-sources">
            {t("ui.running.sources", {sources: copyText(view.sources)})}
          </p>
        )}
        <p className="workbench-summary completed-meta" data-testid="completed-workbench-header">
          {t("ui.running.version", {version: view.version ?? 1})}
          {view.researchCumulativeLabel ? ` · ${copyText(view.researchCumulativeLabel)}` : ""}
          {view.workbenchHeaderSummary ? ` · ${copyText(view.workbenchHeaderSummary)}` : ""}
          {view.windowCumulativeLabel && view.windowCumulativeLabel !== view.workbenchHeaderSummary
            ? ` · ${copyText(view.windowCumulativeLabel)}`
            : ""}
          {view.effective || view.effectiveSeconds != null
            ? ` · ${t("ui.running.effectiveOnly", {
                effective: view.effectiveSeconds != null
                  ? formatDuration(view.effectiveSeconds, t)
                  : copyText(view.effective),
              })}`
            : ""}
          {view.remaining || view.remainingSeconds != null
            ? ` · ${t("ui.running.remaining", {
                remaining: view.remainingSeconds != null
                  ? formatDuration(view.remainingSeconds, t)
                  : copyText(view.remaining),
              })}`
            : ""}
        </p>
        {showFailedGateLine && (
          <p className="failed-gates-line" data-testid="failed-gates-line">
            {t("ui.completed.failedGates", {
              gates: view.failedVerifierIds!.map((id) => copyText(id)).join(t("ui.copy.gateJoiner")),
            })}
          </p>
        )}
        {eligible && view.title && (
          <section className="completed-strategy-summary">
            <h2 data-user-content="true">{view.title}</h2>
          </section>
        )}
        <div className="completed-export-actions" data-testid="completed-export-actions">
          {eligible ? (
            <button
              type="button"
              className="cyan-button"
              data-testid="export-strategy-pack-primary"
              disabled={view.status === "ended"}
              onClick={() => void runExport("strategy_pack")}
            >
              {t("ui.export.strategyPack")}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="stop-button-primary"
                data-testid="export-research-record-primary"
                onClick={() => void runExport("research_record")}
              >
                {t("ui.export.researchRecord")}
              </button>
              <button type="button" className="quiet-button" disabled data-testid="export-strategy-pack-locked">
                {t("ui.export.strategyLocked")}
              </button>
            </>
          )}
        </div>
        {!eligible && (
          <ExportOutcomeMessages
            exportFeedback={exportFeedback}
            openFolderError={openFolderError}
            onReveal={revealExportFolder}
          />
        )}
        {!eligible && view.exportBlockerMessages && view.exportBlockerMessages.length > 0 && (
          <ul className="export-blockers" data-testid="export-blockers">
            {view.exportBlockerMessages.map((message) => (
              <li key={message}>{copyText(message)}</li>
            ))}
          </ul>
        )}
        {!eligible && (
          <details className="completed-tools-details" data-testid="completed-tools-details">
            <summary>{t("ui.completed.tools")}</summary>
            <div className="reverify-panel" data-testid="reverify-panel">
              <p className="eyebrow">{t("ui.completed.reverifyEyebrow")}</p>
              <label>
                {t("ui.completed.round")}
                <select
                  value={reverifyRoundId}
                  onChange={(event) => {
                    const nextRound = event.target.value;
                    setReverifyRoundId(nextRound);
                    const round = reverifyRounds.find((item) => item.roundId === nextRound);
                    const stillThere = round?.methods.some(
                      (item) => item.methodId === reverifyMethodId,
                    );
                    if (round && !stillThere && round.methods[0]) {
                      setReverifyMethodId(round.methods[0].methodId);
                    }
                  }}
                  data-testid="reverify-round-select"
                >
                  {reverifyRounds.map((round) => (
                    <option key={round.roundId} value={round.roundId}>{copyText(round.roundLabel)}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("ui.completed.method")}
                <select
                  value={reverifyMethodId}
                  onChange={(event) => setReverifyMethodId(event.target.value)}
                  data-testid="reverify-method-select"
                >
                  {methodsForRound.map((method) => (
                    <option key={method.methodId} value={method.methodId}>
                      {copyText(method.methodLabel)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="text-button"
                disabled={reverifyBusy}
                aria-busy={reverifyBusy}
                data-testid="reverify-submit"
                onClick={() => void runReverify()}
              >
                {reverifyBusy ? t("ui.completed.reverifyBusy") : t("ui.completed.reverify")}
              </button>
              {view.lastReverification && (
                <p
                  className={
                    view.lastReverification.passed
                      ? "reverify-result"
                      : "reverify-result reverify-result--fail"
                  }
                  data-testid="reverify-result"
                  role="status"
                >
                  {view.lastReverification.userMessage
                    ? copyText(view.lastReverification.userMessage)
                    : t("ui.completed.reverifyResult", {
                      method: copyText(view.lastReverification.methodLabel),
                      result: view.lastReverification.passed ? t("ui.completed.pass") : t("ui.completed.fail"),
                    })}
                </p>
              )}
              {reverifyError && (
                <div className="reverify-error" data-testid="reverify-error" role="alert">
                  <EngineFailureText raw={reverifyError} />
                </div>
              )}
            </div>
            <div className="stacked-field modify-rerun-field">
              <span className="field-label">{t("ui.completed.modify")}</span>
              <input
                value={modification}
                onChange={(event) => setModification(event.target.value)}
                placeholder={t("ui.completed.modifyPlaceholder")}
                aria-label={t("ui.completed.modify")}
              />
              <button
                disabled={!modification.trim()}
                data-testid="confirm-modification-button"
                onClick={() => void (async () => {
                  await api.sendDialogue(view.researchId, modification.trim());
                  await api.confirmModification(view.researchId);
                })()}
              >
                {t("ui.running.confirmModification")}
              </button>
              {!modification.trim() && (
                <p className="field-hint" data-testid="modify-empty-hint">
                  {t("ui.completed.modifyHint")}
                </p>
              )}
            </div>
          </details>
        )}
      {view.symbolSelection && (
        <section className="materials-note completed-data-window" data-testid="completed-symbol-selection">
          <p className="eyebrow">{t("ui.completed.windowEyebrow")}</p>
          <p data-testid="completed-symbol-selection-summary">
            {copyText(view.symbolSelection.summaryLine) ||
              t(view.symbolSelection.count === 1 ? "ui.completed.windowSummaryOne" : "ui.completed.windowSummary", {
                count: view.symbolSelection.count,
                listName: copyText(view.symbolSelection.listName),
                listVersion: view.symbolSelection.listVersion,
              })}
          </p>
          {view.symbolSelection.listNote ? (
            <p data-testid="symbol-selection-note">{copyText(view.symbolSelection.listNote)}</p>
          ) : null}
          {view.symbolSelection.isDefaultPool || view.symbolSelection.source === "default_pool" ? (
            <p data-testid="survivorship-hint">
              <I18nText k="ui.copy.survivorshipHint" />
            </p>
          ) : null}
          {view.symbolSelection.listNote && view.symbolSelection.listVersion ? (
            <p data-testid="symbol-selection-version">
              {t("ui.confirm.listVersion", {version: view.symbolSelection.listVersion})}
            </p>
          ) : null}
          <p>
            {t("ui.completed.windowMeta", {
              start: view.symbolSelection.dataStart,
              end: view.symbolSelection.dataEnd,
              cutoff: view.symbolSelection.dataCutoff,
              backtest: view.backtestCutoff ? t("ui.completed.backtest", {date: view.backtestCutoff}) : "",
              source: copyText(view.symbolSelection.dataSource),
            })}
          </p>
        </section>
      )}
      {view.status !== "ended" && (
        <p className="extend-hint" data-testid="extend-research-hint">
          {t("ui.completed.extendHint")}
        </p>
      )}
      {view.canContinueIterate && (
        <button
          type="button"
          data-testid="continue-iterate"
          onClick={() => {
            const m = view.cumulativeRoundsOnWindow ?? 0;
            const threshold = view.highSuspicionRoundThreshold ?? 20;
            setIterateConfirm({
              title: t("ui.completed.iterateTitle"),
              body: t("ui.completed.iterateBody", {
                window: view.windowCumulativeLabel
                  ? copyText(view.windowCumulativeLabel)
                  : t("ui.completed.iterateFallback", {n: m}),
              }),
              confirmLabel: t("ui.completed.iterateTitle"),
              onConfirm: () => {
                if (m >= threshold) {
                  setIterateConfirm({
                    title: t("ui.completed.suspicionTitle"),
                    body: t("ui.completed.suspicionBody", {n: m, threshold}),
                    confirmLabel: t("ui.completed.suspicionConfirm"),
                    onConfirm: () => {
                      void api.continueIterate(view.researchId, {
                        userConfirmed: true,
                        highSuspicionAcknowledged: true,
                      });
                      setIterateConfirm(null);
                    },
                  });
                  return;
                }
                void api.continueIterate(view.researchId, {
                  userConfirmed: true,
                  highSuspicionAcknowledged: false,
                });
                setIterateConfirm(null);
              },
            });
          }}
        >
          {t("ui.completed.iterateTitle")}
        </button>
      )}
      {view.latePassPresentation?.show && (
        <section className="late-pass-record" data-testid="late-pass-prior-failures">
          <p className="eyebrow">{t("ui.completed.priorEyebrow")}</p>
          <p>
            {view.windowCumulativeLabel
              ? copyText(view.windowCumulativeLabel)
              : t("ui.completed.iterateFallback", {n: view.latePassPresentation.cumulativeRoundsOnWindow})}
            {t("ui.copy.clauseJoin")}{t("ui.completed.priorLead", {round: view.latePassPresentation.conclusionRoundId})}
          </p>
          <ul>
            {view.latePassPresentation.priorFailureRecords.map((record) => (
              <li key={record.roundId}>
                {t("ui.completed.priorItem", {
                  version: record.versionNumber,
                  round: record.roundNumber,
                  cumulative: record.cumulativeRoundOnWindow,
                  gates: record.failedGateIds.join("、") || t("glossary.verification"),
                })}
                {record.paramChanges.length > 0 && (
                  <span>
                    {" "}
                    {t("ui.completed.params", {
                      changes: record.paramChanges.map(([p, a, b]) => `${p}:${a}→${b}`).join(", "),
                    })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {view.overturnedExports && <p>{t("ui.completed.overturned")}</p>}
      {view.anomaly && <AnomalyChecklist anomaly={view.anomaly} />}
      {view.rounds && view.rounds.length > 0 && (
        <section className="completed-rounds" data-testid="completed-round-evidence">
          <p className="eyebrow">{t("ui.completed.roundsEyebrow")}</p>
          {view.rounds.map((round, index) => (
            <article className="round-card" key={round.roundId} data-testid="completed-round-card">
              <small>{t("ui.completed.roundN", {n: (view.rounds?.length ?? 0) - index})}</small>
              <p data-testid="logic-statement"><LogicStatementText text={round.logicStatement.statement} /></p>
              {round.logicStatement.changeDescription && (
                <p className="change-note">{copyText(round.logicStatement.changeDescription)}</p>
              )}
              {round.implementationDelta.modelChangesDisplay && (
                <p>{copyText(round.implementationDelta.modelChangesDisplay)}</p>
              )}
              <p className="round-verdict">
                {round.verificationPassed
                  ? round.pitPassed === false
                    ? t("ui.completed.verdictPit")
                    : t("ui.completed.verdictPass")
                  : t("ui.completed.verdictFail")}
              </p>
            </article>
          ))}
        </section>
      )}
        {eligible && (
          <details className="completed-tools-details">
            <summary>{t("ui.completed.more")}</summary>
            <ExportFeedbackBlock
              exportFeedback={exportFeedback}
              openFolderError={openFolderError}
              onExport={() => void runExport("research_record")}
              onReveal={revealExportFolder}
            />
            <div className="reverify-panel" data-testid="reverify-panel">
              <p className="eyebrow">{t("ui.completed.reverifyEyebrow")}</p>
              <label>
                {t("ui.completed.round")}
                <select
                  value={reverifyRoundId}
                  onChange={(event) => setReverifyRoundId(event.target.value)}
                  data-testid="reverify-round-select"
                >
                  {reverifyRounds.map((round) => (
                    <option key={round.roundId} value={round.roundId}>{copyText(round.roundLabel)}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("ui.completed.method")}
                <select
                  value={reverifyMethodId}
                  onChange={(event) => setReverifyMethodId(event.target.value)}
                  data-testid="reverify-method-select"
                >
                  {methodsForRound.map((method) => (
                    <option key={method.methodId} value={method.methodId}>
                      {copyText(method.methodLabel)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="text-button"
                disabled={reverifyBusy}
                data-testid="reverify-submit"
                onClick={() => void runReverify()}
              >
                {reverifyBusy ? t("ui.completed.reverifyBusy") : t("ui.completed.reverify")}
              </button>
            </div>
            <div className="stacked-field modify-rerun-field">
              <span className="field-label">{t("ui.completed.modify")}</span>
              <input
                value={modification}
                onChange={(event) => setModification(event.target.value)}
                placeholder={t("ui.completed.modifyPlaceholder")}
                aria-label={t("ui.completed.modify")}
              />
              <button
                disabled={!modification.trim()}
                data-testid="confirm-modification-button"
                onClick={() => void (async () => {
                  await api.sendDialogue(view.researchId, modification.trim());
                  await api.confirmModification(view.researchId);
                })()}
              >
                {t("ui.running.confirmModification")}
              </button>
            </div>
          </details>
        )}
        {view.status === "ended" && (
          <label className="extend-hours-field">
            {t("ui.completed.extendLabel")}
            <input value={extensionHours} onChange={(event) => setExtensionHours(event.target.value)} inputMode="decimal" />
            <button onClick={() => void api.extendResearch(view.researchId, Number(extensionHours))}>{t("ui.completed.extendConfirm")}</button>
          </label>
        )}
      </article>
    </div>
  );
}

