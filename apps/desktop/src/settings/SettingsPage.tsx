import {languageFromSystemLocale, languageName} from "../i18n/locale";
import {useI18n} from "../i18n/I18nProvider";
import type {UiLanguagePreference} from "../i18n/types";
import "./settings.css";

export function settingsTab(route: string): "data" | "llm" | "general" {
  if (route.startsWith("#/settings/data")) return "data";
  if (route.startsWith("#/settings/llm")) return "llm";
  return "general";
}

export function SettingsPage({route}: {route: string}) {
  const {t, preference, setPreference, systemLocale} = useI18n();
  const tab = settingsTab(route);
  const followName = languageName(languageFromSystemLocale(systemLocale));
  const languageNotRecorded = t("glossary.languageNotRecorded");
  return (
    <div className="settings-screen" data-testid="settings-page">
      <p className="settings-kicker">
        {t("settings.kicker")} · {t("settings.routeLabel")}
      </p>
      <nav className="settings-tabs" aria-label={t("nav.settings")}>
        <a
          href="#/settings/data"
          className={tab === "data" ? "active" : ""}
          data-testid="settings-tab-data"
        >
          {t("settings.tabs.data")}
        </a>
        <a
          href="#/settings/llm"
          className={tab === "llm" ? "active" : ""}
          data-testid="settings-tab-llm"
        >
          {t("settings.tabs.llm")}
        </a>
        <a
          href="#/settings/general"
          className={tab === "general" ? "active" : ""}
          data-testid="settings-tab-general"
          aria-current={tab === "general" ? "page" : undefined}
        >
          {t("settings.tabs.general")}
        </a>
      </nav>
      {tab === "general" ? (
        <div className="settings-grid">
          <section className="settings-card" aria-labelledby="ui-language-title">
            <h2 id="ui-language-title">{t("settings.general.title")}</h2>
            <p>{t("settings.general.immediate")}</p>
            <div className="settings-options" role="radiogroup" aria-labelledby="ui-language-title">
              <LanguageOption
                value="system"
                checked={preference === "system"}
                title={t("settings.general.followSystem", {languageName: followName})}
                hint={t("settings.general.followHint")}
                badge={t("settings.general.defaultBadge")}
                onSelect={setPreference}
              />
              <LanguageOption
                value="zh"
                checked={preference === "zh"}
                title={t("settings.general.optionZh")}
                onSelect={setPreference}
              />
              <LanguageOption
                value="en"
                checked={preference === "en"}
                title={t("settings.general.optionEn")}
                onSelect={setPreference}
              />
            </div>
            <p>{t("settings.general.ruleSystem")}</p>
            <p>{t("settings.general.ruleManual")}</p>
            <p>{t("settings.general.stored")}</p>
          </section>
          <section className="settings-card" aria-labelledby="ui-language-scope">
            <h2 id="ui-language-scope">{t("settings.scope.title")}</h2>
            <p className="settings-scope-label">{t("settings.scope.switchesLabel")}</p>
            <ul>
              <li>{t("settings.scope.switchUi")}</li>
              <li>{t("settings.scope.switchPages")}</li>
              <li>{t("settings.scope.switchNames")}</li>
              <li>{t("settings.scope.switchErrors")}</li>
              <li>{t("settings.scope.switchExport")}</li>
              <li>{t("settings.scope.switchLlm")}</li>
            </ul>
            <p className="settings-scope-label">{t("settings.scope.keepsLabel")}</p>
            <ul>
              <li>{t("settings.scope.keepNotes")}</li>
              <li>{t("settings.scope.keepSaved")}</li>
              <li>{t("settings.scope.keepLiterature")}</li>
              <li>{t("settings.scope.keepNames")}</li>
              <li>{t("settings.scope.keepLegacy", {languageNotRecorded})}</li>
            </ul>
            <p>
              {t("settings.scope.footnote", {
                datePattern: t("format.datePattern"),
                dateTimePattern: t("format.dateTimePattern"),
              })}
            </p>
          </section>
        </div>
      ) : (
        <section className="settings-card" data-testid="settings-later">
          <p>{t("settings.later.body")}</p>
        </section>
      )}
    </div>
  );
}

function LanguageOption({
  value,
  checked,
  title,
  hint,
  badge,
  onSelect,
}: {
  value: UiLanguagePreference;
  checked: boolean;
  title: string;
  hint?: string;
  badge?: string;
  onSelect: (preference: UiLanguagePreference) => Promise<void>;
}) {
  return (
    <label className={`settings-option${checked ? " selected" : ""}`} data-testid={`ui-language-option-${value}`}>
      <input
        type="radio"
        name="ui-language"
        value={value}
        checked={checked}
        onChange={() => void onSelect(value)}
      />
      <span className="settings-option-body">
        <strong>{title}</strong>
        {hint ? <small>{hint}</small> : null}
      </span>
      {badge ? <span className="settings-badge">{badge}</span> : null}
    </label>
  );
}
