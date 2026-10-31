import {FormEvent, useEffect, useRef, useState} from "react";

import {I18nText} from "../i18n/I18nText";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import {baseUrlIsAcceptable, isLoopbackBaseUrl, llmRecordLabel} from "./llmSettingsCommand";
import {tauriLlmSettingsPort, type LlmSettingsPort} from "./llmSettingsPort";

const SENT_KEYS = [
  "settings.llm.sent1",
  "settings.llm.sent2",
  "settings.llm.sent3",
  "settings.llm.sent4",
] as const satisfies readonly MessageKey[];

const NOT_SENT_KEYS = [
  "settings.llm.notSent1",
  "settings.llm.notSent2",
  "settings.llm.notSent3",
  "settings.llm.notSent4",
  "settings.llm.notSent5",
  "settings.llm.notSent6",
  "settings.llm.notSent7",
] as const satisfies readonly MessageKey[];

export function LlmSettingsCard({port = tauriLlmSettingsPort}: {port?: LlmSettingsPort}) {
  const {t} = useI18n();
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiKeySet, setApiKeySet] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [clearKey, setClearKey] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const apiKeyRef = useRef<HTMLInputElement>(null);
  const local = isLoopbackBaseUrl(baseUrl);
  const record = llmRecordLabel(baseUrl, model);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([port.load(), port.apiKeyIsSet()]).then(([snapshot, keySet]) => {
      if (cancelled) return;
      setBaseUrl(snapshot.baseUrl);
      setModel(snapshot.model);
      setPrivacy(snapshot.privacyAcknowledged);
      setApiKeySet(keySet);
    });
    return () => {
      cancelled = true;
    };
  }, [port]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    if (!privacy) {
      setError(t("settings.llm.privacyRequired"));
      return;
    }
    if (!baseUrlIsAcceptable(baseUrl) || !model.trim()) {
      setError(t("settings.llm.baseUrlInvalid"));
      return;
    }
    const key = apiKey.trim();
    if (!local && !key && !apiKeySet) {
      setError(t("settings.llm.remoteKeyRequired"));
      return;
    }
    setError("");
    void (async () => {
      await port.save({baseUrl, model, privacyAcknowledged: privacy});
      if (clearKey) {
        await port.clearApiKey();
        setApiKeySet(false);
        setClearKey(false);
      } else if (key) {
        await port.setApiKey(key);
        setApiKeySet(true);
        setApiKey("");
      }
      setSaved(true);
    })();
  };

  return (
    <section className="settings-card" data-testid="settings-llm">
      <h2><I18nText k="settings.llm.title" /></h2>
      <p><I18nText k="settings.llm.intro" /></p>
      <p data-testid="llm-optional"><I18nText k="settings.llm.optional" /></p>
      <form className="llm-form" data-focus-ring="cyan" onSubmit={onSubmit}>
        <label className="llm-field">
          <span><I18nText k="settings.llm.baseUrl" /></span>
          <input
            data-testid="llm-base-url"
            name="baseUrl"
            autoComplete="off"
            spellCheck={false}
            value={baseUrl}
            onChange={(event) => {
              setBaseUrl(event.target.value);
              setSaved(false);
            }}
            placeholder="http://127.0.0.1:11434/v1"
          />
        </label>
        <p data-testid="llm-local-status">
          <strong><I18nText k="settings.llm.local" /></strong>
          {" "}
          <I18nText k={local ? "settings.llm.localHint" : "settings.llm.remoteHint"} />
        </p>
        <label className="llm-field">
          <span><I18nText k="settings.llm.apiKey" /></span>
          <input
            ref={apiKeyRef}
            data-testid="llm-api-key"
            name="apiKey"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(event) => {
              setApiKey(event.target.value);
              setSaved(false);
            }}
          />
        </label>
        {local ? <p data-testid="llm-no-key"><I18nText k="settings.llm.noKey" /></p> : null}
        {apiKeySet ? <p data-testid="llm-key-stored"><I18nText k="settings.llm.keyStored" /></p> : null}
        {apiKeySet ? (
          <label className="llm-check">
            <input
              data-testid="llm-clear-key"
              type="checkbox"
              checked={clearKey}
              onChange={(event) => setClearKey(event.target.checked)}
            />
            <I18nText k="settings.llm.clearKey" />
          </label>
        ) : null}
        <label className="llm-field">
          <span><I18nText k="settings.llm.model" /></span>
          <input
            data-testid="llm-model"
            name="model"
            autoComplete="off"
            spellCheck={false}
            value={model}
            onChange={(event) => {
              setModel(event.target.value);
              setSaved(false);
            }}
            placeholder="gpt-4.1-mini"
          />
        </label>
        <div className="llm-actions">
          <button type="button" className="quiet-button" data-testid="llm-test-connection">
            <I18nText k="settings.llm.testConnection" />
          </button>
          <button
            type="button"
            className="quiet-button"
            data-testid="llm-replace-key"
            onClick={() => {
              setApiKey("");
              setSaved(false);
              apiKeyRef.current?.focus();
            }}
          >
            <I18nText k="settings.llm.replaceKey" />
          </button>
        </div>
        <p data-testid="llm-test-only"><I18nText k="settings.llm.testOnly" /></p>
        <div className="llm-impl" data-testid="llm-impl">
          <p className="llm-impl-title"><I18nText k="settings.llm.implTitle" /></p>
          <p><I18nText k="settings.llm.implBody" params={{record}} /></p>
        </div>
        <div className="llm-disclosure" data-testid="llm-disclosure">
          <h3><I18nText k="settings.llm.sectionSent" /></h3>
          <p data-testid="llm-review"><I18nText k="settings.llm.reviewBeforeSaving" /></p>
          <p data-testid="llm-host-leaves"><I18nText k="settings.llm.hostLeaves" /></p>
        </div>
        <div className="llm-columns" data-testid="llm-columns">
          <div data-testid="llm-sent">
            <p className="llm-col-title"><I18nText k="settings.llm.sent" /></p>
            <ul>
              {SENT_KEYS.map((key) => (
                <li key={key}><I18nText k={key} /></li>
              ))}
            </ul>
          </div>
          <div data-testid="llm-not-sent">
            <p className="llm-col-title"><I18nText k="settings.llm.notSent" /></p>
            <ul>
              {NOT_SENT_KEYS.map((key) => (
                <li key={key}><I18nText k={key} /></li>
              ))}
            </ul>
          </div>
        </div>
        <label className="llm-check">
          <input
            data-testid="llm-privacy"
            type="checkbox"
            checked={privacy}
            onChange={(event) => {
              setPrivacy(event.target.checked);
              setSaved(false);
            }}
          />
          <I18nText k="settings.llm.privacy" />
        </label>
        {error ? <p className="llm-error" data-testid="llm-error" role="alert">{error}</p> : null}
        {saved ? <p data-testid="llm-saved"><I18nText k="settings.llm.saved" /></p> : null}
        {!privacy ? <p data-testid="llm-save-hint"><I18nText k="settings.data.consentHint" /></p> : null}
        <button type="submit" className="cyan-button" data-testid="llm-save" disabled={!privacy}>
          <I18nText k="settings.llm.save" />
        </button>
      </form>
    </section>
  );
}
