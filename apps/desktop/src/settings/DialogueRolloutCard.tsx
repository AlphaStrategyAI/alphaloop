import {useEffect, useState} from "react";

import {I18nText} from "../i18n/I18nText";
import {useI18n} from "../i18n/I18nProvider";
import {DISABLED_DIALOGUE_ROLLOUT, type DialogueRolloutSnapshot} from "./dialogueRolloutCommand";
import {tauriDialogueRolloutPort, type DialogueRolloutPort} from "./dialogueRolloutPort";

export function DialogueRolloutCard({
  port = tauriDialogueRolloutPort,
}: {
  port?: DialogueRolloutPort;
}) {
  const {t} = useI18n();
  const [snapshot, setSnapshot] = useState<DialogueRolloutSnapshot>(DISABLED_DIALOGUE_ROLLOUT);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void port.load().then((next) => {
      if (cancelled) return;
      setSnapshot(next);
      setLoaded(true);
    });
    return () => {
      cancelled = true;
    };
  }, [port]);

  const onToggle = () => {
    const next = !snapshot.enabled;
    setError("");
    setSnapshot({...snapshot, enabled: next});
    void port.save(next).then(
      (saved) => setSnapshot(saved),
      () => {
        setSnapshot({...snapshot, enabled: !next});
        setError(t("settings.dialogue.rollback"));
      },
    );
  };

  return (
    <section
      className="settings-card"
      aria-labelledby="dialogue-rollout-title"
      data-testid="dialogue-rollout-card"
      data-loaded={loaded ? "true" : "false"}
      data-dialogue-default={snapshot.enabled ? "on" : "off"}
      data-write-gate={snapshot.gateClosed ? "closed" : "open"}
    >
      <h2 id="dialogue-rollout-title">
        <I18nText k="settings.dialogue.title" />
      </h2>
      <p>
        <I18nText k="settings.dialogue.lead" />
      </p>
      <label className="settings-dialogue-toggle">
        <input
          type="checkbox"
          data-testid="dialogue-rollout-enabled"
          checked={snapshot.enabled}
          onChange={onToggle}
        />
        <span data-testid="dialogue-rollout-status">
          {snapshot.enabled ? t("settings.dialogue.on") : t("settings.dialogue.off")}
        </span>
      </label>
      <p data-testid="dialogue-rollout-when-off">
        <I18nText k="settings.dialogue.whenOff" />
      </p>
      <p data-testid="dialogue-rollout-rollback">
        <I18nText k="settings.dialogue.rollback" />
      </p>
      <p data-testid="dialogue-rollout-packaging">
        <I18nText k="settings.dialogue.packaging" />
      </p>
      <p data-testid="dialogue-rollout-gate">
        {snapshot.gateClosed
          ? t("settings.dialogue.gateClosed", {reason: snapshot.gateReason || snapshot.gateDetail})
          : t("settings.dialogue.gateOpen")}
      </p>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
