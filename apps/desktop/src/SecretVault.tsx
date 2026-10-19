import {FormEvent, useEffect, useState} from "react";
import {invoke} from "@tauri-apps/api/core";

import {secretVaultCopy as copy} from "./secret-vault-copy";

type VaultStatus = {backend: string; locked: boolean};

export function SecretVaultButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" data-testid="secret-vault-open" onClick={() => setOpen(true)}>
        {copy.open}
      </button>
      {open ? <SecretVaultPanel onClose={() => setOpen(false)} /> : null}
    </>
  );
}

export function SecretVaultPanel({onClose}: {onClose: () => void}) {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [alias, setAlias] = useState("vendor-demo");
  const [secret, setSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [isSet, setIsSet] = useState(false);
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

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setFailure("");
    await invoke("secret_set", {
      id: alias,
      value: secret,
      passphrase: passphrase || null,
    });
    setSecret("");
    setNote(copy.saved);
    await refresh();
  }

  return (
    <div className="secret-vault-backdrop" data-testid="secret-vault">
      <form className="tech-pulse-card secret-vault-panel" onSubmit={(event) => void onSave(event)}>
        <header>
          <h2>{copy.title}</h2>
          <button type="button" onClick={onClose}>{copy.close}</button>
        </header>
        {status?.backend === "needs_choice" ? (
          <div data-testid="secret-fallback">
            <p>{copy.needsChoice}</p>
            <button type="button" onClick={() => void invoke("secret_choose_fallback", {choice: "memory"}).then(() => refresh())}>
              {copy.memory}
            </button>
            <button type="button" onClick={() => void invoke("secret_choose_fallback", {choice: "passphrase"}).then(() => refresh())}>
              {copy.passphraseFile}
            </button>
          </div>
        ) : null}
        {status?.backend === "keyring" ? <p>{copy.keyring}</p> : null}
        {status?.backend === "memory" ? <p>{copy.memoryNote}</p> : null}
        {status?.locked ? <p data-testid="secret-locked">{copy.locked}</p> : null}
        <p data-testid="secret-status">{isSet ? copy.set : copy.unset}</p>
        <label>
          {copy.alias}
          <input value={alias} onChange={(event) => setAlias(event.target.value)} data-testid="secret-alias" />
        </label>
        <label>
          {copy.secret}
          <input
            type="password"
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
            data-testid="secret-value"
            autoComplete="off"
          />
        </label>
        {status?.backend === "passphrase" ? (
          <label>
            {copy.passphrase}
            <input
              type="password"
              value={passphrase}
              onChange={(event) => setPassphrase(event.target.value)}
              data-testid="secret-passphrase"
              autoComplete="off"
            />
            <span>{copy.passphraseHint}</span>
          </label>
        ) : null}
        <div className="secret-vault-actions">
          {status?.locked ? (
            <button
              type="button"
              onClick={() => void invoke("secret_unlock", {passphrase}).then(() => refresh())}
            >
              {copy.unlock}
            </button>
          ) : null}
          <button type="submit" disabled={status?.backend === "needs_choice"}>{copy.save}</button>
          <button
            type="button"
            onClick={() => void invoke("secret_delete", {id: alias}).then(() => refresh())}
          >
            {copy.remove}
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
            {copy.preview}
          </button>
        </div>
        {note ? <p>{note}</p> : null}
        {failure ? <p data-testid="secret-failure-text">{failure}</p> : null}
      </form>
    </div>
  );
}
