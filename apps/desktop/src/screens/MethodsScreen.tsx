import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import {useFocusTrap} from "../dialogFocus";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, ScorecardDimension, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import {localizeEngineSurface} from "../i18n/engineSurface";
import {localizeKnownCopy} from "../i18n/productCopy";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";

export function MethodDetail({api, method}: {api: DesktopApi; method: ValidationMethod}) {
  const {t, resolved} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const surface = (text: string | null | undefined) =>
    text ? localizeEngineSurface(copyText(text), t, resolved) : "";
  const originalBody = method.definitionDisplay ?? method.description;
  const [reviseOpen, setReviseOpen] = useState(false);
  const [reviseBody, setReviseBody] = useState(originalBody);
  const dialogRef = useRef<HTMLDivElement>(null);
  const rememberedDimensions = useRef<{id: string; dimensions: readonly ScorecardDimension[]}>({
    id: method.id,
    dimensions: method.dimensions ?? [],
  });
  useFocusTrap(reviseOpen, dialogRef);
  useEffect(() => {
    if (!reviseOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setReviseBody(originalBody);
      setReviseOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [reviseOpen, originalBody]);
  if (rememberedDimensions.current.id !== method.id) {
    rememberedDimensions.current = {id: method.id, dimensions: method.dimensions ?? []};
  } else if (method.dimensions && method.dimensions.length > 0) {
    rememberedDimensions.current = {id: method.id, dimensions: method.dimensions};
  }
  const dimensions = method.dimensions && method.dimensions.length > 0
    ? method.dimensions
    : rememberedDimensions.current.dimensions;
  const cancelEdit = () => {
    setReviseBody(originalBody);
    setReviseOpen(false);
  };
  const comparisonLabel = (dim: NonNullable<ValidationMethod["dimensions"]>[number]) =>
    dim.comparisonLabel ??
    ({gt: t("ui.methods.gt"), gte: t("ui.methods.gte"), eq: t("ui.methods.eq"), lt: t("ui.methods.lt"), lte: t("ui.methods.lte")} as const)[dim.comparison];
  return (
    <section className="method-detail">
      <h2 className="method-title">{copyText(method.name)}</h2>
      {method.category && <span className="method-category-badge">{surface(method.category)}</span>}
      {method.description && !method.description.trim().startsWith("{") ? (
        <p>{surface(method.description)}</p>
      ) : null}
      <div className="method-definition-display" data-testid="method-definition-display">
        {surface(method.definitionDisplay ?? method.description)}
      </div>
      <details className="method-advanced">
        <summary>{t("ui.methods.advanced")}</summary>
        <code className="revision-id" title={method.revision}>{method.revision}</code>
      </details>
      {method.usageCount != null && (
        <p>{t("ui.methods.used", {count: method.usageCount})}</p>
      )}
      {dimensions.length > 0 && (
        <div className="scorecard-dimensions" data-testid="scorecard-dimensions">
          <p className="eyebrow">{t("ui.methods.dimensions")}</p>
          <table>
            <thead>
              <tr>
                <th>{t("ui.methods.colKind")}</th>
                <th>{t("ui.methods.colName")}</th>
                <th>{t("ui.methods.colThreshold")}</th>
                <th>{t("ui.methods.colCompare")}</th>
                <th>{t("ui.methods.colFailure")}</th>
              </tr>
            </thead>
            <tbody>
              {dimensions.map((dim) => (
                <tr key={`${dim.kind}-${dim.name}`}>
                  <td>{surface(dim.kindLabel ?? dim.kind)}</td>
                  <td>{surface(dim.name)}</td>
                  <td>{dim.passThreshold}</td>
                  <td>{surface(comparisonLabel(dim))}</td>
                  <td>{surface(dim.failureDisplay)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button className="quiet-button" type="button" onClick={() => {
        setReviseBody(originalBody);
        setReviseOpen(true);
      }}>{t("ui.methods.edit")}</button>
      <p>{t("ui.methods.stillOld")}</p>
      {reviseOpen && (
        <div className="in-app-confirm-backdrop" data-testid="revise-method-dialog" data-dim="0.5" onMouseDown={(event) => {
          if (event.target === event.currentTarget) cancelEdit();
        }}>
          <div ref={dialogRef} className="in-app-confirm-card revise-method-card" role="dialog" aria-modal="true" aria-labelledby="revise-method-title">
            <div className="revise-method-head">
              <h2 id="revise-method-title">{t("ui.methods.edit")}</h2>
              <button
                type="button"
                className="dialog-close"
                data-testid="revise-method-close"
                aria-label={t("ui.shell.close")}
                onClick={cancelEdit}
              >
                ✕
              </button>
            </div>
            <p>{t("ui.methods.editLead")}</p>
            <label>
              {t("ui.methods.bodyLabel")}
              <textarea
                value={reviseBody}
                onChange={(event) => setReviseBody(event.target.value)}
                rows={6}
              />
            </label>
            <div className="in-app-confirm-actions">
              <button type="button" data-dialog-cancel="" onClick={cancelEdit}>{t("ui.methods.cancel")}</button>
              <button
                type="button"
                className="cyan-button"
                disabled={!reviseBody.trim()}
                onClick={() => {
                  void api.reviseMethod(method.id, reviseBody.trim());
                  setReviseOpen(false);
                }}
              >
                {t("ui.methods.createRevision")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function MethodsScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "methods"}>}) {
  const {t} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const selected = view.methods.find((item) => item.id === view.selected) ?? view.methods[0];
  const [name, setName] = useState("");
  const [definition, setDefinition] = useState("");
  return (
    <div className="methods-layout" data-testid="methods-layout" data-split="40/60">
      <aside className="method-list" data-surface="deep" data-aside-fill="#0B0E13">
        <header className="methods-chrome" data-testid="methods-chrome">
          <h1>{t("ui.methods.pageTitle")}</h1>
          <p>{t("ui.methods.listLead")}</p>
        </header>
        <details className="method-create">
          <summary>{t("ui.methods.create")}</summary>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder={t("ui.methods.namePlaceholder")} />
          <input value={definition} onChange={(event) => setDefinition(event.target.value)} placeholder={t("ui.methods.definitionPlaceholder")} />
          <button className="quiet-button" onClick={() => {
            if (name.trim() && definition.trim()) void api.createMethod(name.trim(), definition.trim());
          }}>{t("ui.methods.create")}</button>
        </details>
        {view.methods.map((method) => (
          <a
            className={method.id === selected?.id ? "active" : undefined}
            href={`#/methods/${encodeURIComponent(method.id)}`}
            key={method.id}
          >
            {copyText(method.name)}
            <small className="revision-label">
              {copyText((method as {revisionLabel?: string}).revisionLabel) || t("ui.methods.builtin")}
            </small>
            {method.usageCount != null ? (
              <small>{t("ui.methods.used", {count: method.usageCount})}</small>
            ) : null}
          </a>
        ))}
      </aside>
      {selected && <MethodDetail api={api} method={selected} />}
    </div>
  );
}
