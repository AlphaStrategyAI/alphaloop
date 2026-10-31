import {FormEvent, useEffect, useLayoutEffect, useRef, useState} from "react";
import {createPortal} from "react-dom";
import {invoke} from "@tauri-apps/api/core";

import {useFocusTrap} from "./dialogFocus";
import {I18nText} from "./i18n/I18nText";
import {useI18n} from "./i18n/I18nProvider";

type VaultStatus = {backend: string; locked: boolean};

export function SecretVaultButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="rail-secrets" data-testid="secret-vault-open" onClick={() => setOpen(true)}>
        <svg className="rail-icon" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M8 11V8a4 4 0 1 1 8 0v3M7 11h10v8H7v-8z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <I18nText k="ui.secrets.open" />
      </button>
      {open
        ? createPortal(
            <SecretVaultPanel onClose={() => setOpen(false)} />,
            document.body,
          )
        : null}
    </>
  );
}

export function SecretVaultPanel({onClose}: {onClose: () => void}) {
  const {t} = useI18n();
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [alias, setAlias] = useState("vendor-demo");
  const [secret, setSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [isSet, setIsSet] = useState(false);
  const [saved, setSaved] = useState(false);
  const [note, setNote] = useState("");
  const [failure, setFailure] = useState("");

  async function refresh(nextAlias = alias) {
    const next = await invoke<VaultStatus>("secret_store_status");
    setStatus(next);
    if (next.backend !== "needs_choice") {
      setIsSet(await invoke<boolean>("secret_is_set", {id: nextAlias}));
    } else {
      setIsSet(false);
    }
  }

  useEffect(() => {
    void refresh().catch((error: unknown) => setNote(String(error)));
  }, []);

  useLayoutEffect(() => {
    const node = document.querySelector<HTMLElement>("[data-testid=secret-vault]");
    // Read layout once so WebKit paints the overlay immediately instead of
    // waiting for a window resize.
    if (node) void node.getBoundingClientRect();
  }, []);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setFailure("");
    await invoke("secret_set", {
      id: alias,
      value: secret,
      passphrase: passphrase || null,
    });
    setSecret("");
    setSaved(true);
    setNote("");
    await refresh();
  }

  const locked = Boolean(status?.locked);
  const showEntries = Boolean(status) && !locked && status?.backend !== "needs_choice";
  const panelRef = useRef<HTMLFormElement>(null);
  useFocusTrap(true, panelRef, locked ? "[data-testid=secret-passphrase]" : "[data-dialog-cancel]");

  return (
    <div
      className="secret-vault-backdrop"
      data-testid="secret-vault"
      data-dim="0.5"
      data-disclosure={locked ? "locked" : showEntries ? "entries" : "setup"}
      data-backend={status?.backend ?? ""}
      data-locked={locked ? "true" : "false"}
      role="presentation"
      style={{position: "fixed", inset: 0, zIndex: 80, pointerEvents: "auto"}}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        ref={panelRef}
        className="tech-pulse-card secret-vault-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="secret-vault-title"
        onSubmit={(event) => void onSave(event)}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="secret-vault-head">
          <h2 id="secret-vault-title"><I18nText k="ui.secrets.title" /></h2>
          <button
            type="button"
            className="dialog-close"
            data-dialog-cancel=""
            data-testid="secret-vault-close"
            aria-label={t("ui.secrets.close")}
            onClick={onClose}
          >
            ✕
          </button>
        </header>
        {status?.backend === "needs_choice" ? (
          <div data-testid="secret-fallback">
            <p><I18nText k="ui.secrets.needsChoice" /></p>
            <button type="button" onClick={() => void invoke("secret_choose_fallback", {choice: "memory"}).then(() => refresh())}>
              <I18nText k="ui.secrets.memory" />
            </button>
            <button
              type="button"
              data-testid="secret-choose-passphrase"
              onClick={() => void invoke("secret_choose_fallback", {choice: "passphrase"}).then(() => refresh())}
            >
              <I18nText k="ui.secrets.passphraseFile" />
            </button>
          </div>
        ) : null}
        {!locked && status?.backend === "keyring" ? <p><I18nText k="ui.secrets.keyring" /></p> : null}
        {!locked && status?.backend === "memory" ? <p><I18nText k="ui.secrets.memoryNote" /></p> : null}
        {locked ? (
          <p data-testid="secret-locked"><I18nText k="ui.secrets.locked" /></p>
        ) : status ? (
          <p data-testid="secret-status">
            <I18nText k={isSet ? "ui.secrets.set" : "ui.secrets.unset"} />
          </p>
        ) : null}
        {showEntries ? (
          <div data-testid="secret-entry-list">
            <label>
              <I18nText k="ui.secrets.alias" />
              <input value={alias} onChange={(event) => setAlias(event.target.value)} data-testid="secret-alias" />
            </label>
            <label>
              <I18nText k="ui.secrets.secret" />
              <input
                type="password"
                value={secret}
                onChange={(event) => setSecret(event.target.value)}
                data-testid="secret-value"
                autoComplete="off"
              />
            </label>
          </div>
        ) : null}
        {locked ? (
          <label data-testid="secret-passphrase-field">
            <I18nText k="ui.secrets.passphrase" />
            <input
              type="password"
              value={passphrase}
              onChange={(event) => setPassphrase(event.target.value)}
              data-testid="secret-passphrase"
              autoComplete="off"
            />
            <span><I18nText k="ui.secrets.passphraseHint" /></span>
          </label>
        ) : null}
        <div className="secret-vault-actions" style={{whiteSpace: "nowrap"}}>
          {locked ? (
            <button
              type="button"
              data-testid="secret-unlock"
              onClick={() => void invoke("secret_unlock", {passphrase}).then(() => refresh())}
            >
              <I18nText k="ui.secrets.unlock" />
            </button>
          ) : showEntries ? (
            <>
              <button type="submit" data-testid="secret-save" disabled={status?.backend === "needs_choice"}>
                <I18nText k="ui.secrets.save" />
              </button>
              <button
                type="button"
                className="danger-button"
                data-testid="secret-delete"
                onClick={() => void invoke("secret_delete", {id: alias}).then(() => refresh())}
              >
                <I18nText k="ui.secrets.remove" />
              </button>
              <button
                type="button"
                data-testid="secret-failure-preview"
                onClick={() =>
                  void invoke<string>("secret_failure_preview", {id: alias}).then((message) => {
                    setFailure(message);
                  })
                }
              >
                <I18nText k="ui.secrets.preview" />
              </button>
            </>
          ) : null}
        </div>
        {saved ? <p><I18nText k="ui.secrets.saved" /></p> : null}
        {note ? <p>{note}</p> : null}
        {failure ? <p data-testid="secret-failure-text">{failure}</p> : null}
      </form>
    </div>
  );
}
