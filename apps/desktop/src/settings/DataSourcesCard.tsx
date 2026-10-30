import {useState, type ReactNode} from "react";

import {I18nText} from "../i18n/I18nText";
import {useI18n} from "../i18n/I18nProvider";

const VENDORS = ["Sharadar", "EODHD", "Financial Modeling Prep", "Tiingo", "Massive"] as const;
const CONSENT_KEY = "alphaloop.data-source-consent";

/**
 * Settings data tab. Honesty sentences and the unlicensed acknowledgement
 * are the existing product copy; this surface does not shorten them.
 * Save stays disabled until that acknowledgement is checked.
 */
export function DataSourcesCard() {
  const {t} = useI18n();
  const [acknowledged, setAcknowledged] = useState(() => {
    try {
      return localStorage.getItem(CONSENT_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [saved, setSaved] = useState(false);
  return (
    <div className="settings-data" data-testid="settings-data">
      <section className="honesty-card" data-testid="honesty-sentences">
        <h2><I18nText k="glossary.readyToRun" /></h2>
        <p>{t("ui.confirm.poolNoteMembers")}</p>
        <p>{t("ui.confirm.poolNoteIndexOnly")}</p>
        <p>{t("ui.confirm.poolNoteEdgarUnconfirmed")}</p>
      </section>

      <h2>{t("settings.data.builtin")}</h2>
      <SourceCard
        title={t("settings.data.yahoo")}
        badge={t("glossary.unlicensed")}
        badgeTone="stop"
        testId="source-yahoo"
      >
        <p>{t("ui.confirm.unlicensedNotice")}</p>
        <p>{t("settings.data.noKeyNoTest")}</p>
      </SourceCard>
      <SourceCard
        title={t("settings.data.akshare")}
        badge={t("glossary.unlicensed")}
        badgeTone="stop"
        testId="source-akshare"
      >
        <p>{t("ui.confirm.unlicensedNotice")}</p>
        <p>{t("settings.data.noKeyNoTest")}</p>
      </SourceCard>

      <h2>{t("settings.data.mine")}</h2>
      <SourceCard title={t("settings.data.localFile")} testId="source-local">
        <p data-testid="settings-later">{t("settings.later.body")}</p>
        <p>{t("settings.data.suggestOnly")}</p>
      </SourceCard>

      <h2>{t("settings.data.vendors")}</h2>
      {VENDORS.map((name) => (
        <SourceCard
          key={name}
          title={name}
          badge={t("glossary.notYetSupported")}
          badgeTone="mute"
          testId={`vendor-${name}`}
        >
          <p>{t("settings.data.vendorNoTest")}</p>
        </SourceCard>
      ))}

      <div className="settings-consent-row">
        <label className="llm-check">
          <input
            data-testid="data-consent"
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => {
              const checked = event.target.checked;
              setAcknowledged(checked);
              setSaved(false);
              if (!checked) {
                try {
                  localStorage.removeItem(CONSENT_KEY);
                } catch {
                  /* private mode */
                }
              }
            }}
          />
          <span>{t("ui.confirm.unlicensedAck")}</span>
        </label>
        <button
          type="button"
          className="cyan-button"
          data-testid="data-save"
          disabled={!acknowledged}
          onClick={() => {
            if (!acknowledged) return;
            try {
              localStorage.setItem(CONSENT_KEY, "1");
            } catch {
              /* private mode */
            }
            setSaved(true);
          }}
        >
          {t("settings.llm.save")}
        </button>
      </div>
      {!acknowledged ? (
        <p className="settings-save-hint" data-testid="data-save-hint">{t("settings.data.consentHint")}</p>
      ) : null}
      {saved ? <p data-testid="data-saved">{t("settings.llm.saved")}</p> : null}
    </div>
  );
}

function SourceCard({
  title,
  badge,
  badgeTone = "mute",
  testId,
  children,
}: {
  title: string;
  badge?: string;
  badgeTone?: "stop" | "mute";
  testId: string;
  children: ReactNode;
}) {
  return (
    <article className="source-card" data-testid={testId}>
      <header>
        <h3>{title}</h3>
        {badge ? <span className={`source-badge source-badge--${badgeTone}`}>{badge}</span> : null}
      </header>
      {children}
    </article>
  );
}
