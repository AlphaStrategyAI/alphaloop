import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import {localizeKnownCopy, researchListTitle} from "../i18n/productCopy";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {
  RESEARCH_LIST_FILTERS,
  listRowStatusKey,
  matchesResearchListFilter,
  researchListFilterKey,
  type ResearchListFilter,
} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";

function researchHref(researchId: string): string {
  return `#/research/${researchId}`;
}

function OpenResearchLink({
  researchId,
  className,
  children,
}: {
  researchId: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <a
      className={className}
      href={researchHref(researchId)}
      data-research-id={researchId}
      onClick={(event) => {
        event.preventDefault();
        const id = event.currentTarget.dataset.researchId;
        if (!id) return;
        window.location.hash = researchHref(id);
      }}
    >
      {children}
    </a>
  );
}

function RowDelete({onDelete}: {onDelete: () => void}) {
  const {t} = useI18n();
  return (
    <>
      <button
        type="button"
        className="row-delete icon-button"
        aria-label={t("ui.list.deleteTitle")}
        onClick={onDelete}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 7h14M9 7V5h6v2M8 7l1 12h6l1-12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      <details className="row-more">
        <summary className="row-more-summary" data-testid="research-row-more" aria-label={t("ui.list.more")}>⋯</summary>
        <button type="button" data-testid="delete-research" onClick={onDelete}>{t("ui.list.delete")}</button>
      </details>
    </>
  );
}

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
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const researchTitle = (title: string) => researchListTitle(title, t);
  const deleteWarning = t("ui.list.deleteBody");
  const [deleteConfirm, setDeleteConfirm] = useState<InAppConfirmRequest | null>(null);
  const [filter, setFilter] = useState<ResearchListFilter>("all");
  const awaitingCards = [
    ...(view.awaiting ? [view.awaiting] : []),
    ...view.rows.filter(
      (row) => row.status === "awaiting_confirm" && row.id !== view.awaiting?.id,
    ),
  ];
  const confirmCards = view.rows.filter((row) => row.status === "confirm_run");
  const rows = view.rows.filter(
    (row) => row.status !== "confirm_run" && row.status !== "awaiting_confirm",
  );
  const visibleAwaiting = awaitingCards.filter((item) => matchesResearchListFilter(item.status, filter));
  const visibleConfirm = confirmCards.filter((item) => matchesResearchListFilter(item.status, filter));
  const visibleRows = rows.filter((row) => matchesResearchListFilter(row.status, filter));
  const hasAny = awaitingCards.length + confirmCards.length + rows.length > 0;
  const askDelete = (researchId: string) => {
    setDeleteConfirm({
      title: t("ui.list.deleteTitle"),
      body: deleteWarning,
      confirmLabel: t("ui.list.delete"),
      tone: "danger",
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
        <div className="list-header-row">
          <div>
            <h1 className="list-title">{t("ui.list.title")}</h1>
            <p className="list-tagline">{t("ui.list.tagline")}</p>
          </div>
          <button
            className="cyan-button list-new-research"
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
        </div>
        <div
          className="list-filters"
          role="toolbar"
          aria-label={t("ui.list.filters")}
          data-testid="research-list-filters"
        >
          {RESEARCH_LIST_FILTERS.map((id) => (
            <button
              key={id}
              type="button"
              className="list-filter-chip"
              data-testid={`research-list-filter-${id}`}
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
            >
              {t(researchListFilterKey(id))}
            </button>
          ))}
        </div>
      </header>
      {!hasAny ? (
        <div className="list-empty-panel" data-testid="research-list-empty">
          <p className="list-empty">{t("ui.list.empty")}</p>
        </div>
      ) : null}
      {visibleAwaiting.map((item) => (
        <article
          className="awaiting-primary list-pinned-card"
          data-kind="awaiting-primary"
          data-testid="awaiting-pinned-card"
          data-research-id={item.id}
          key={item.id}
        >
          <div className="list-pinned-head">
            <StatusPill status="awaiting_confirm" />
            <span className="list-pinned-meta">{t("ui.list.frozen")}</span>
          </div>
          <OpenResearchLink className="awaiting-primary-body" researchId={item.id}>
            <h2>{researchTitle(item.title)}</h2>
            <p>
              <span>{item.universeLabel ? copyText(item.universeLabel) : t("ui.list.unlocked")}</span>
              {item.createdAt
                ? ` · ${formatResearchTimestamp(item.createdAt)}`
                : ""}
            </p>
          </OpenResearchLink>
          <div className="list-pinned-actions">
            <OpenResearchLink className="cyan-button list-open-confirm" researchId={item.id}>
              {t("ui.list.openCard")}
            </OpenResearchLink>
            <span className="list-pinned-hint">{t("ui.list.clickCard")}</span>
            <RowDelete onDelete={() => askDelete(item.id)} />
          </div>
        </article>
      ))}
      {visibleConfirm.map((item) => (
        <article
          className="awaiting-primary list-pinned-card list-pinned-confirm"
          data-kind="confirm-pinned"
          data-testid="confirm-pinned-card"
          data-research-id={item.id}
          key={item.id}
        >
          <div className="list-pinned-head">
            <StatusPill status="confirm_run" />
          </div>
          <OpenResearchLink className="awaiting-primary-body" researchId={item.id}>
            <h2>{researchTitle(item.title)}</h2>
            <p>{item.universeLabel ? copyText(item.universeLabel) : t("ui.list.briefReady")}</p>
          </OpenResearchLink>
          <div className="list-pinned-actions">
            <OpenResearchLink className="cyan-button list-open-confirm" researchId={item.id}>
              {t("ui.list.openCard")}
            </OpenResearchLink>
          </div>
        </article>
      ))}
      <div className="research-rows">
        {visibleRows.map((row) => (
          <article
            className={`research-row${row.status === "ended" ? " research-row--failed" : ""}`}
            data-testid="research-row"
            data-research-id={row.id}
            data-status={row.status}
            key={row.id}
          >
            <div>
              <h3>{researchTitle(row.title)}</h3>
              <p>
                <span>{row.universeLabel ? copyText(row.universeLabel) : t("ui.list.unlocked")}</span>
                {row.createdAt ? ` · ${formatResearchTimestamp(row.createdAt)}` : ""}
                {row.updatedAt ? ` · ${t("ui.list.updated", {time: formatResearchTimestamp(row.updatedAt)})}` : ""}
              </p>
            </div>
            <div className="row-actions">
              <OpenResearchLink className="cyan-button list-enter" researchId={row.id}>{t("ui.list.enter")}</OpenResearchLink>
              <RowDelete onDelete={() => askDelete(row.id)} />
              <StatusPill status={row.status} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

