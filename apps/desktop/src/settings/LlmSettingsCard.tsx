import {FormEvent, useEffect, useState} from "react";

import {I18nText} from "../i18n/I18nText";
import {useI18n} from "../i18n/I18nProvider";
import {baseUrlIsAcceptable, isLoopbackBaseUrl} from "./llmSettingsCommand";
import {tauriLlmSettingsPort, type LlmSettingsPort} from "./llmSettingsPort";

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
  const local = isLoopbackBaseUrl(baseUrl);

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
      <form className="llm-form" onSubmit={onSubmit}>
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
        <p><I18nText k="settings.llm.sent" /></p>
        <p><I18nText k="settings.llm.notSent" /></p>
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
