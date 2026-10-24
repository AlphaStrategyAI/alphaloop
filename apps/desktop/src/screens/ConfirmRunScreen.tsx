import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, DialogueTurnView, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {I18nText} from "../i18n/I18nText";
import {ConfirmDataNoticeText, ConstructionNoticeText} from "../i18n/marketDataCopy";
import {DialogueTurnBody, EngineFailureText} from "../i18n/engineFailure";
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
  const {t, resolved} = useI18n();
  const resolution = view.symbolResolution ?? null;
  const listSep = resolved === "zh" ? "、" : ", ";
  const localeList = (value: string | null | undefined) =>
    (value ?? "").split("、").filter(Boolean).join(listSep);
  const seeded = resolution
    ? resolution.symbols.length
      ? resolution.symbols.join(listSep)
      : localeList(resolution.token)
    : "";
  const [symbolDraft, setSymbolDraft] = useState(seeded);
  const [saving, setSaving] = useState(false);
  const saveChain = useRef(Promise.resolve());
  useEffect(() => {
    setSymbolDraft(seeded);
  }, [seeded, view.researchId]);
  const commitSymbol = (value: string) => {
    const text = value.trim();
    if (text === seeded.trim()) return Promise.resolve();
    setSaving(true);
    const job = saveChain.current.then(() => api.setResearchSymbol(view.researchId, text));
    saveChain.current = job.then(
      () => undefined,
      () => undefined,
    );
    return job.finally(() => setSaving(false));
  };
  const exchangeDigits = resolution?.token?.match(/\d{6}/)?.[0];
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
  const [pickedSource, setPickedSource] = useState("");
  const [acked, setAcked] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const startingRef = useRef(false);
  const sel = view.symbolSelection;
  const returnToDraft = () => {
    void api.unlockBrief(view.researchId);
  };
  const dirty = symbolDraft.trim() !== seeded.trim();
  const runBlocked = Boolean(resolution?.blocked) && !dirty;
  const offeredId = sel?.offeredDataSourceId ?? "";
  const catalog = sel?.priceSources ?? [];
  const catalogMode = catalog.length > 0;
  const selectedId = pickedSource || (sel?.dataSourcePending ? "" : sel?.dataSourceId || "");
  const selectedChoice = catalog.find((item) => item.id === selectedId);
  const unlicensedIds = new Set(["yahoo_daily", "akshare_sina_daily"]);
  const alreadyAcked = Boolean(sel?.unlicensedAcknowledgedAt);
  const ackRequired = catalogMode
    ? Boolean(selectedChoice?.unlicensed && !selectedChoice.acknowledgedAt)
    : unlicensedIds.has(selectedId) && !alreadyAcked;
  const mustPick = catalogMode || sel?.dataSourcePending === true || sel?.unlicensedAcknowledgementRequired === true;
  const canRun = (!mustPick || Boolean(selectedId)) && (!ackRequired || acked) && !runBlocked;
  const startRun = () => {
    if (startingRef.current || !canRun) return;
    startingRef.current = true;
    setStarting(true);
    setRunError(null);
    void (async () => {
      try {
        if (symbolDraft.trim() !== seeded.trim()) {
          await commitSymbol(symbolDraft);
        }
        await api.confirmRun(view.researchId, {
          dataSourceId: selectedId || undefined,
          unlicensedAcknowledged: ackRequired ? true : undefined,
        });
      } catch (error: unknown) {
        setRunError(error instanceof Error ? error.message : String(error));
      } finally {
        startingRef.current = false;
        setStarting(false);
      }
    })();
  };
  const blockMessage = () => {
    if (!resolution?.blocked) return null;
    if (resolution.code === "SYMBOL_NO_DATA") {
      return t("ui.confirm.noData", {symbol: localeList(resolution.symbol)});
    }
    if (resolution.code === "SYMBOL_ETF_UNSUPPORTED") {
      return t("ui.confirm.etfUnsupported", {symbol: localeList(resolution.symbol)});
    }
    if (resolution.code === "SYMBOL_MIXED_MARKETS") {
      return t("ui.confirm.mixedMarkets", {
        cn_symbols: localeList(resolution.cnSymbols),
        us_symbols: localeList(resolution.usSymbols),
      });
    }
    if (resolution.code === "SYMBOL_MARKET_MISMATCH") {
      const mismatches = resolution.mismatches ?? [];
      const market = t(resolution.mismatchMarket === "US" ? "ui.confirm.marketUs" : "ui.confirm.marketCn");
      return t("ui.confirm.marketMismatch", {
        market,
        symbols: mismatches.join(listSep),
        n: mismatches.length || 1,
      });
    }
    if (resolution.code === "SYMBOL_ASK_PENDING" || resolution.code === "SYMBOL_AMOUNT_LIKE") {
      return null;
    }
    return t("ui.confirm.unresolved", {token: localeList(resolution.token)});
  };
  const asks = resolution?.asks ?? [];
  const answers = resolution?.answers ?? [];
  const hints = (resolution?.hints ?? []).slice(0, 3);
  const removeRecognized = (symbol: string) => {
    const rest = (resolution?.symbols ?? []).filter((item) => item !== symbol);
    void api.setResearchSymbol(view.researchId, rest.join(listSep));
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
      {view.marketSwitch && (
        <p className="confirm-lead" data-testid="market-switch-notice">
          {t("ui.confirm.marketSwitched", {
            market: t(view.marketSwitch.market === "US" ? "ui.confirm.marketUs" : "ui.confirm.marketCn"),
            benchmark: view.marketSwitch.benchmark,
          })}
        </p>
      )}
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
      {resolution?.editable && (
        <section className="confirm-data-panel symbol-resolution" data-testid="symbol-resolution">
          {resolution.inferred.length > 0 && (
            <p data-testid="symbol-recognition">
              {t("ui.confirm.recognized", {
                symbol: resolution.inferred.map((item) => item.symbol).join(listSep),
              })}
              {resolution.inferred.map((item) => (
                <button
                  key={item.symbol}
                  type="button"
                  className="text-button symbol-remove"
                  data-testid={`symbol-remove-${item.symbol}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => removeRecognized(item.symbol)}
                >
                  {t("ui.confirm.removeSymbol", {symbol: item.symbol})}
                </button>
              ))}
            </p>
          )}
          {asks.map((ask) => (
            <div key={ask.token} className="symbol-ask" data-testid="symbol-ask" data-ask-kind={ask.kind ?? "ask"}>
              <p>
                {ask.kind === "amount"
                  ? t("ui.confirm.amountAsk", {token: ask.token, symbol: ask.symbol})
                  : ask.kind === "finance"
                    ? t("ui.confirm.financeAsk", {token: ask.token, symbol: ask.symbol})
                    : ask.token.toUpperCase() === ask.symbol.toUpperCase()
                      ? t("ui.confirm.symbolAskSame", {symbol: ask.symbol})
                      : t("ui.confirm.symbolAsk", {token: ask.token, symbol: ask.symbol})}
              </p>
              <button
                type="button"
                className="text-button"
                data-testid={`symbol-ask-yes-${ask.token}`}
                onClick={() => api.answerSymbolAsk(view.researchId, ask.token, true)}
              >
                {t("ui.confirm.useAsSymbol")}
              </button>
              <button
                type="button"
                className="text-button"
                data-testid={`symbol-ask-no-${ask.token}`}
                onClick={() => api.answerSymbolAsk(view.researchId, ask.token, false)}
              >
                {t("ui.confirm.justText")}
              </button>
            </div>
          ))}
          {answers.map((answer) => (
            <p key={answer.token} data-testid="symbol-ask-answered">
              {answer.accept
                ? t("ui.confirm.usedAsSymbol", {symbol: answer.symbol})
                : t("ui.confirm.treatedAsText", {token: answer.token})}
              <button
                type="button"
                className="text-button"
                data-testid={`symbol-ask-change-${answer.token}`}
                onClick={() => api.revertSymbolAsk(view.researchId, answer.token)}
              >
                {t("ui.confirm.changeAnswer")}
              </button>
            </p>
          ))}
          {(resolution?.unrecognized ?? []).map((item) => (
            <p key={item.token} data-testid={`symbol-unrecognized-${item.token}`}>
              {t("ui.confirm.unrecognizedTicker", {token: item.token})}
            </p>
          ))}
          {hints.length === 1 && (
            <div className="symbol-pool-hint" data-testid="symbol-pool-hint">
              <p>
                {t((resolution?.poolCount ?? 0) === 1 ? "ui.confirm.poolHintOne" : "ui.confirm.poolHint", {
                  n: resolution?.poolCount ?? 0,
                  symbol: hints[0].symbol,
                })}
              </p>
              <button
                type="button"
                className="text-button"
                data-testid="symbol-hint-use"
                onClick={() => api.useHintedSymbol(view.researchId, hints[0].symbol)}
              >
                {t("ui.confirm.setAsSymbol")}
              </button>
            </div>
          )}
          {hints.length > 1 && (
            <div className="symbol-pool-hint" data-testid="symbol-pool-hint">
              <p>
                {t((resolution?.poolCount ?? 0) === 1 ? "ui.confirm.poolHintManyOne" : "ui.confirm.poolHintMany", {
                  n: resolution?.poolCount ?? 0,
                })}
              </p>
              {hints.map((hint, index) => (
                <button
                  key={hint.token}
                  type="button"
                  className="text-button"
                  data-testid={`symbol-hint-use-${index + 1}`}
                  onClick={() => api.useHintedSymbol(view.researchId, hint.symbol)}
                >
                  {hint.symbol} {t("ui.confirm.setAsSymbol")}
                </button>
              ))}
            </div>
          )}
          {resolution?.code === "SYMBOL_MARKET_MISMATCH" &&
            (resolution.mismatches ?? []).map((symbol) => (
              <button
                key={symbol}
                type="button"
                className="text-button"
                data-testid={`symbol-remove-mismatch-${symbol}`}
                onClick={() => api.dismissMismatchedSymbol(view.researchId, symbol)}
              >
                {t("ui.confirm.removeSymbol", {symbol})}
              </button>
            ))}
          {resolution?.code === "SYMBOL_MIXED_MARKETS" && (
            <div data-testid="symbol-mixed-actions">
              <button
                type="button"
                className="text-button"
                data-testid="symbol-remove-cn"
                onClick={() => api.removeMarketSide(view.researchId, "cn")}
              >
                {t("ui.confirm.removeCn")}
              </button>
              <button
                type="button"
                className="text-button"
                data-testid="symbol-remove-us"
                onClick={() => api.removeMarketSide(view.researchId, "us")}
              >
                {t("ui.confirm.removeUs")}
              </button>
            </div>
          )}
          {blockMessage() && (
            <p className="confirm-data-notice" data-testid="symbol-block-error" role="alert">
              {blockMessage()}
            </p>
          )}
          <label className="symbol-edit-label">
            <span>{t("ui.confirm.symbolEdit")}</span>
            <input
              data-testid="symbol-edit"
              value={symbolDraft}
              aria-label={t("ui.confirm.symbolEdit")}
              onChange={(event) => setSymbolDraft(event.target.value)}
              onBlur={() => {
                void commitSymbol(symbolDraft);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void commitSymbol(symbolDraft);
                }
              }}
            />
          </label>
          {resolution.blocked && resolution.code === "SYMBOL_UNRESOLVED" && exchangeDigits && (
            <div role="group" aria-label={t("ui.confirm.pickExchange")}>
              {(["SH", "SZ", "BJ"] as const).map((suffix) => (
                <button
                  key={suffix}
                  type="button"
                  className="text-button"
                  data-testid={`symbol-pick-${suffix}`}
                  onClick={() => api.setResearchSymbol(view.researchId, `${exchangeDigits}.${suffix}`)}
                >
                  .{suffix}
                </button>
              ))}
            </div>
          )}
        </section>
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
              t(sel.count === 1 ? "ui.confirm.summaryOne" : "ui.confirm.summary", {
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
          <p className="confirm-data-meta" data-testid="confirm-data-meta">
            {t("ui.confirm.meta", {
              start: sel.dataStart,
              end: sel.dataEnd,
              source: selectedChoice ? copyText(selectedChoice.label) : copyText(sel.dataSource),
            })}
          </p>
          {catalogMode && (
            <div className="confirm-source-choice" data-testid="price-source-picker">
              {selectedChoice?.unlicensed && (
                <p className="confirm-data-footnote" data-testid="unlicensed-notice">
                  {t("ui.confirm.unlicensedNotice")}
                </p>
              )}
              {catalog.map((item) => (
                <label className="confirm-source-option" key={item.id}>
                  <input
                    type="radio"
                    name={`price-source-${view.researchId}`}
                    data-testid={`price-source-${item.id}`}
                    checked={selectedId === item.id}
                    onChange={() => {
                      setPickedSource(item.id);
                      setAcked(false);
                    }}
                  />
                  <span>{copyText(item.label)}</span>
                  {item.unlicensed && (
                    <span className="unlicensed-tag" data-testid="unlicensed-tag">
                      {t("glossary.unlicensed")}
                    </span>
                  )}
                </label>
              ))}
            </div>
          )}
          {!catalogMode && sel.dataSourcePending && offeredId && (
            <div className="confirm-source-choice" data-testid="unlicensed-source-choice-row">
              <p className="confirm-data-footnote" data-testid="unlicensed-notice">
                {t("ui.confirm.unlicensedNotice")}
              </p>
              <label className="confirm-source-option">
                <input
                  type="checkbox"
                  data-testid="unlicensed-source-choice"
                  checked={pickedSource === offeredId}
                  onChange={(event) => {
                    setPickedSource(event.target.checked ? offeredId : "");
                    setAcked(false);
                  }}
                />
                <span>
                  {t("ui.confirm.chooseSource", {source: copyText(sel.offeredDataSource || offeredId)})}
                  {" · "}
                  {t("glossary.unlicensed")}
                </span>
              </label>
            </div>
          )}
          {ackRequired && (
            <label className="confirm-source-option" data-testid="unlicensed-ack-row">
              <input
                type="checkbox"
                data-testid="unlicensed-ack"
                checked={acked}
                onChange={(event) => setAcked(event.target.checked)}
              />
              <span>{t("ui.confirm.unlicensedAck")}</span>
            </label>
          )}
          {selectedChoice?.unlicensed && selectedChoice.acknowledgedAt && (
            <p className="confirm-data-footnote" data-testid="unlicensed-ack-done">
              {t("ui.confirm.unlicensedAcked", {
                date: formatResearchTimestamp(selectedChoice.acknowledgedAt),
              })}
            </p>
          )}
          {!catalogMode && alreadyAcked && selectedId && sel.unlicensedAcknowledgedAt && (
            <p className="confirm-data-footnote" data-testid="unlicensed-ack-done">
              {t("ui.confirm.unlicensedAcked", {
                date: formatResearchTimestamp(sel.unlicensedAcknowledgedAt),
              })}
            </p>
          )}
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
      {runError && (
        <p className="confirm-run-error" data-testid="confirm-run-error" role="alert">
          <EngineFailureText raw={runError} />
        </p>
      )}
      <div className="actions confirm-actions">
        {asks.length > 0 && (
          <p className="confirm-data-notice" data-testid="symbol-ask-block-hint">
            {t("ui.confirm.askBeforeRun")}
          </p>
        )}
        <button
          className="cyan-button"
          data-testid="confirm-run-start"
          disabled={starting || saving || !canRun}
          aria-busy={starting || saving}
          onMouseDown={(event) => event.preventDefault()}
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

