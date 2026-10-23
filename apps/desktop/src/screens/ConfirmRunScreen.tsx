import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, DialogueTurnView, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {I18nText} from "../i18n/I18nText";
import {ConfirmDataNoticeText, ConstructionNoticeText} from "../i18n/marketDataCopy";
import {DialogueTurnBody} from "../i18n/engineFailure";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
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

function Settings({
  values,
  onEditSlot,
}: {
  values: Extract<DesktopView, {kind: "draft" | "confirm_run"}>["settings"];
  onEditSlot?: (slot: BriefSlotName) => void;
}) {
  const {t} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const settingLabels: readonly [BriefSlotName, string][] = [
    ["thesis", t("ui.brief.thesis")],
    ["universe", t("ui.brief.universe")],
    ["max_effective_hours", t("ui.brief.hours")],
    ["round1_methods", t("ui.brief.methods")],
    ["coverage_floor", t("ui.brief.coverage")],
  ];
  return (
    <aside className="settings">
      <p className="eyebrow">{t("ui.brief.eyebrow")}</p>
      {settingLabels.map(([key, label]) => (
        <div className="settings-row" data-testid={`brief-slot-${key}`} key={key}>
          <dt className="settings-label">{label}</dt>
          <dd
            className={`settings-value${key === "thesis" ? " settings-value-prose" : ""}`}
            data-testid={key === "thesis" ? "brief-thesis-value" : undefined}
          >
            {key === "thesis"
              ? values.thesis
                ? renderSettingsProse(values.thesis)
                : t("ui.list.unlocked")
              : copyText(values[key]) || t("ui.list.unlocked")}
            {key === "universe" && values.universe_symbol_chips && values.universe_symbol_chips.length > 0 ? (
              <span className="universe-symbol-chips" data-testid="universe-symbol-chips">
                {values.universe_symbol_chips.map((symbol) => (
                  <span className="symbol-chip" key={symbol}>{symbol}</span>
                ))}
              </span>
            ) : key === "universe" && values.universe_symbols ? (
              <span className="universe-symbols" data-testid="universe-symbols">
                {copyText(values.universe_symbols)}
              </span>
            ) : null}
          </dd>
          {onEditSlot ? (
            <button
              className="text-button slot-edit settings-action"
              type="button"
              data-testid={`edit-slot-${key}`}
              onClick={() => onEditSlot(key)}
            >
              {t("ui.brief.edit")}
            </button>
          ) : (
            <span className="settings-action" />
          )}
        </div>
      ))}
    </aside>
  );
}

function DialoguePanel({
  researchId,
  api,
  dialogue,
  chatEnabled = true,
  title,
}: {
  researchId: string;
  api: DesktopApi;
  dialogue: readonly DialogueTurnView[];
  chatEnabled?: boolean;
  title?: string;
}) {
  const {t} = useI18n();
  const heading = title ?? t("ui.dialogue.title");
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || !chatEnabled) return;
    try {
      await api.sendDialogue(researchId, text);
      setMessage("");
    } catch {
      /* mutation error banner */
    }
  };
  useEffect(() => {
    const node = document.querySelector(".conversation");
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [dialogue.length]);

  return (
    <section className="conversation">
      <h1>{heading}</h1>
      <p className="message assistant system" data-testid="dialogue-system-intro">
        {t("ui.dialogue.intro")}
      </p>
      {dialogue.map((turn, index) => (
        <DialogueTurnBody turn={turn} key={index} />
      ))}
      {chatEnabled && (
        <form onSubmit={submit}>
          <input
            data-testid="dialogue-input"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={t("ui.dialogue.placeholder")}
          />
        </form>
      )}
    </section>
  );
}

export function DraftScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "draft"}>}) {
  return (
    <div className="draft-layout">
      <DialoguePanel
        api={api}
        researchId={view.researchId}
        dialogue={view.dialogue}
        chatEnabled
      />
      <Settings values={view.settings} />
    </div>
  );
}

export function ConfirmRunScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  const {t} = useI18n();
  return (
    <div className="draft-layout confirm-run-layout">
      <DialoguePanel
        api={api}
        researchId={view.researchId}
        dialogue={view.dialogue}
        chatEnabled={view.chatEnabled ?? false}
        title={t("ui.status.confirmRun")}
      />
      <ConfirmRunCard api={api} view={view} />
    </div>
  );
}

export function ConfirmRunCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  const {t} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const editSlot = (slot: BriefSlotName) => {
    void api.unlockBrief(view.researchId, slot).then(() => {
      requestAnimationFrame(() => {
        const node = document.querySelector(".conversation");
        if (node && "scrollTo" in node && typeof node.scrollTo === "function") {
          node.scrollTo({top: node.scrollHeight, behavior: "smooth"});
        } else if (node) {
          node.scrollTop = node.scrollHeight;
        }
      });
    });
  };
  const [symbolsOpen, setSymbolsOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const startingRef = useRef(false);
  const sel = view.symbolSelection;
  const returnToDraft = () => {
    void api.unlockBrief(view.researchId);
  };
  const startRun = () => {
    if (startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    void api
      .confirmRun(view.researchId)
      .catch(() => {
        /* bindDesktopApi already recorded the message */
      })
      .finally(() => {
        startingRef.current = false;
        setStarting(false);
      });
  };
  return (
    <article className="confirm-card tech-pulse-card confirm-card-layout" data-testid="confirm-run-card">
      <p className="tech-pulse-eyebrow">Confirm to run</p>
      <h1>{t("ui.status.confirmRun")}</h1>
      <p className="confirm-lead">
        {t("ui.confirm.lead")}
      </p>
      <details className="confirm-policy-details" data-testid="confirm-policy-details">
        <summary>{t("ui.confirm.policy")}</summary>
        <div className="confirm-policy-body">
          <p>{t("ui.confirm.policy1")}</p>
          <p>{t("ui.confirm.policy2")}</p>
          <p>{t("ui.confirm.policy3")}</p>
        </div>
      </details>
      {view.meanReversionOnlyNotice && (
        <p className="confirm-lead" data-testid="mean-reversion-only-notice">
          {copyText(view.meanReversionOnlyNotice)}
        </p>
      )}
      {view.constructionNotice && (
        <p className="confirm-lead" data-testid="construction-notice">
          <ConstructionNoticeText text={view.constructionNotice} />
        </p>
      )}
      {view.confirmDataNotice && (
        <p className="confirm-data-notice" data-testid="confirm-data-notice" role="alert">
          <ConfirmDataNoticeText
            text={view.confirmDataNotice}
            code={view.confirmDataNoticeCode}
            params={view.confirmDataNoticeParams}
          />
        </p>
      )}
      {sel && (
        <section className="confirm-data-panel" data-testid="symbol-selection">
          <div className="confirm-data-panel-head">
            <p className="confirm-data-panel-title">{t("ui.confirm.dataTitle")}</p>
            <button
              type="button"
              className="text-button confirm-data-expand"
              data-testid="toggle-symbol-list"
              onClick={() => setSymbolsOpen((open) => !open)}
            >
              {symbolsOpen ? t("ui.confirm.collapse") : t("ui.confirm.expand")}
            </button>
          </div>
          <p className="confirm-data-summary" data-testid="symbol-selection-summary">
            {copyText(sel.summaryLine) ||
              t("ui.confirm.summary", {
                count: sel.count,
                listName: copyText(sel.listName),
                listVersion: sel.listVersion,
                pool: sel.isDefaultPool || sel.source === "default_pool"
                  ? t("ui.confirm.defaultPool")
                  : t("ui.confirm.userPool", {note: copyText(sel.overrideNote) || t("ui.confirm.userPoolFallback")}),
              })}
          </p>
          {sel.listNote ? (
            <p className="confirm-data-meta" data-testid="symbol-selection-note">{copyText(sel.listNote)}</p>
          ) : null}
          {sel.listNote && sel.listVersion ? (
            <p className="confirm-data-footnote" data-testid="symbol-selection-version">
              {t("ui.confirm.listVersion", {version: sel.listVersion})}
            </p>
          ) : null}
          <p className="confirm-data-meta">
            {t("ui.confirm.meta", {start: sel.dataStart, end: sel.dataEnd, source: copyText(sel.dataSource)})}
          </p>
          <p className="confirm-data-footnote">{t("ui.confirm.footnote")}</p>
          {sel.isDefaultPool || sel.source === "default_pool" ? (
            <div data-testid="default-pool-notes">
              <p className="confirm-data-meta" data-testid="default-pool-note"><I18nText k="ui.confirm.poolNoteMembers" /></p>
              <p className="confirm-data-meta" data-testid="default-pool-note"><I18nText k="ui.confirm.poolNoteIndexOnly" /></p>
              <p className="confirm-data-meta" data-testid="default-pool-note"><I18nText k="ui.confirm.poolNoteEdgarUnconfirmed" /></p>
            </div>
          ) : null}
          {sel.shrinkNote && (
            <p className="pool-shrink-note" data-testid="pool-shrink-note">{copyText(sel.shrinkNote)}</p>
          )}
          {symbolsOpen && (
            <ul className="symbol-ticker-list" data-testid="symbol-ticker-list">
              {sel.symbols.map((symbol) => (
                <li key={symbol}>{symbol}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      <Settings values={view.settings} onEditSlot={editSlot} />
      <div className="actions confirm-actions">
        <button
          className="cyan-button"
          data-testid="confirm-run-start"
          disabled={starting}
          aria-busy={starting}
          onClick={startRun}
        >
          {starting ? t("ui.confirm.starting") : t("glossary.run")}
        </button>
        <button type="button" className="quiet-button" data-testid="confirm-return-draft" onClick={returnToDraft}>
          {t("ui.confirm.editAgain")}
        </button>
      </div>
    </article>
  );
}

