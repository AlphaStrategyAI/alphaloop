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

export function AwaitingConfirmCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "awaiting_confirm"}>}) {
  const {t} = useI18n();
  const [whoPays, setWhoPays] = useState("");
  const isCoverage = view.confirmKind === "coverage";
  const hasEvidence = view.whyChange && view.whyChange.length > 0;
  const canApproveEconomic = isCoverage || hasEvidence;
  const handleApprove = () => {
    void api.resolveConfirm(view.researchId, "approve_new_version", whoPays.trim() || undefined);
  };
  return (
    <article className="awaiting-card tech-pulse-card" data-testid="awaiting-confirm-card">
      <p className="tech-pulse-eyebrow">{t("ui.awaiting.eyebrow")}</p>
      <p className="eyebrow">{t("ui.awaiting.version", {version: view.version})}</p>
      <h1>{isCoverage ? t("ui.awaiting.coverageTitle") : t("ui.awaiting.economicTitle")}</h1>
      <section><small>{t("ui.awaiting.proposed")}</small><p>{view.proposed}</p></section>
      <section><small>{t("ui.awaiting.reason")}</small><p>{view.reason}</p></section>
      <section><small>{t("ui.awaiting.effect")}</small><p>{view.effect}</p></section>
      {view.whyChange && view.whyChange.length > 0 && (
        <section className="evidence-section">
          <small>{t("ui.awaiting.evidence")}</small>
          <ul className="evidence-list">
            {view.whyChange.map((ref) => (
              <li key={ref.recordId}>
                <span className="evidence-kind">{ref.kind}</span>
                <span className="evidence-id">{ref.recordId}</span>
                {ref.summary && <span className="evidence-summary">{ref.summary}</span>}
                <span className="evidence-time">{formatResearchTimestamp(ref.recordedAt)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!isCoverage && (
        <section className="who-pays-section">
          <small>{t("ui.awaiting.whoPays")}</small>
          <textarea
            value={whoPays}
            onChange={(e) => setWhoPays(e.target.value)}
            placeholder={t("ui.awaiting.whoPaysPlaceholder")}
            className="who-pays-input"
          />
        </section>
      )}
      {isCoverage ? (
        <div className="decision-stack coverage-decisions" data-testid="coverage-decisions">
          <button className="cyan-button" onClick={() => void api.resolveConfirm(view.researchId, "accept_lower_floor")}>
            {t("ui.awaiting.acceptFloor")}
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "supply_local_materials")}>
            {t("ui.awaiting.supplyMaterials")}
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "redefine_scope")}>
            {t("ui.awaiting.redefine")}
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "pause_and_edit")}>{t("ui.awaiting.pauseEdit")}</button>
        </div>
      ) : (
        <div className="decision-stack" data-testid="economic-decisions">
          {!hasEvidence && (
            <p className="evidence-required-hint">{t("ui.awaiting.needEvidence")}</p>
          )}
          <button className="cyan-button" onClick={handleApprove} disabled={!canApproveEconomic}>
            {t("ui.awaiting.approve")}
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "reject_keep_logic")}>{t("ui.awaiting.reject")}</button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "pause_and_edit")}>{t("ui.awaiting.pauseEdit")}</button>
        </div>
      )}
    </article>
  );
}

