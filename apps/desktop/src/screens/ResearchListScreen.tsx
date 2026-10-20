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

export function StatusPill({status}: {status: ResearchListDisplayStatus}) {
  const {t} = useI18n();
  return (
    <span className={`status-pill status-pill-dot ${status}`} data-testid="list-status-pill">
      <span className="pill-dot" aria-hidden />
      {t(listRowStatusKey(status))}
    </span>
  );
}

export function ResearchList({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "research_list"}>}) {
  const {t} = useI18n();
  const deleteWarning = t("ui.list.deleteBody");
  const [deleteConfirm, setDeleteConfirm] = useState<InAppConfirmRequest | null>(null);
  const awaiting = view.awaiting;
  const confirmPinned = view.rows.find((row) => row.status === "confirm_run");
  const rows = view.rows.filter((row) => row.status !== "confirm_run");
  const askDelete = (researchId: string) => {
    setDeleteConfirm({
      title: t("ui.list.deleteTitle"),
      body: deleteWarning,
      confirmLabel: t("ui.list.delete"),
      onConfirm: () => {
        void api.deleteResearch(researchId);
        setDeleteConfirm(null);
      },
    });
  };
  return (
    <div className="browse list-screen">
      <InAppConfirmOverlay request={deleteConfirm} onClose={() => setDeleteConfirm(null)} />
      <header className="list-header">
        <div>
          <p className="tech-pulse-eyebrow">{t("nav.research")}</p>
          <h1 className="list-title">{t("ui.list.title")}</h1>
          <p className="list-tagline">{t("ui.list.tagline")}</p>
        </div>
        <button
          className="quiet-button list-new-research"
          data-testid="new-research-button"
          onClick={() => {
            void api.createDraft().then((id) => {
              window.location.hash = `#/research/${id}`;
            });
          }}
        >
          <span className="list-new-research-icon" aria-hidden>+</span>
          {t("ui.list.newResearch")}
        </button>
      </header>
      {awaiting && (
        <article className="awaiting-primary list-pinned-card" data-kind="awaiting-primary">
          <div className="list-pinned-head">
            <StatusPill status="awaiting_confirm" />
            <span className="list-pinned-meta">{t("ui.list.frozen")}</span>
          </div>
          <a className="awaiting-primary-body" href={`#/research/${awaiting.id}`}>
            <h2>{awaiting.title}</h2>
            <p>
              <span>{awaiting.universeLabel ?? t("ui.list.unlocked")}</span>
              {awaiting.createdAt
                ? ` · ${formatResearchTimestamp(awaiting.createdAt)}`
                : ""}
            </p>
          </a>
          <div className="list-pinned-actions">
            <a className="cyan-button list-open-confirm" href={`#/research/${awaiting.id}`}>
              {t("ui.list.openCard")}
            </a>
            <span className="list-pinned-hint">{t("ui.list.clickCard")}</span>
            <button type="button" className="text-button" onClick={() => askDelete(awaiting.id)}>
              {t("ui.list.delete")}
            </button>
          </div>
        </article>
      )}
      {confirmPinned && (
        <article
          className="awaiting-primary list-pinned-card list-pinned-confirm"
          data-kind="confirm-pinned"
          data-testid="confirm-pinned-card"
        >
          <div className="list-pinned-head">
            <StatusPill status="confirm_run" />
          </div>
          <a className="awaiting-primary-body" href={`#/research/${confirmPinned.id}`}>
            <h2>{confirmPinned.title}</h2>
            <p>{confirmPinned.universeLabel ?? t("ui.list.briefReady")}</p>
          </a>
          <div className="list-pinned-actions">
            <a className="cyan-button list-open-confirm" href={`#/research/${confirmPinned.id}`}>
              {t("ui.list.openCard")}
            </a>
          </div>
        </article>
      )}
      <div className="research-rows">
        {rows.map((row) => (
          <article
            className={`research-row${row.status === "ended" ? " research-row--failed" : ""}`}
            data-testid="research-row"
            key={row.id}
          >
            <div>
              <h3>{row.title}</h3>
              <p>
                <span>{row.universeLabel ?? t("ui.list.unlocked")}</span>
                {row.createdAt ? ` · ${formatResearchTimestamp(row.createdAt)}` : ""}
                {row.updatedAt ? ` · ${t("ui.list.updated", {time: formatResearchTimestamp(row.updatedAt)})}` : ""}
              </p>
            </div>
            <div className="row-actions">
              <a href={`#/research/${row.id}`}>{t("ui.list.enter")}</a>
              <button onClick={() => askDelete(row.id)}>{t("ui.list.delete")}</button>
              <StatusPill status={row.status} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

