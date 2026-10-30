import type {ReactNode} from "react";

import {appVersion, gitSha} from "../buildInfo";
import {I18nText} from "../i18n/I18nText";
import {languageFromSystemLocale, languageName} from "../i18n/locale";
import {useI18n} from "../i18n/I18nProvider";
import type {UiLanguagePreference} from "../i18n/types";
import {DataSourcesCard} from "./DataSourcesCard";
import {LlmSettingsCard} from "./LlmSettingsCard";
import type {LlmSettingsPort} from "./llmSettingsPort";
import "./settings.css";

export function settingsTab(route: string): "data" | "llm" | "general" {
  if (route.startsWith("#/settings/data")) return "data";
  if (route.startsWith("#/settings/llm")) return "llm";
  return "general";
}

export function SettingsPage({route, llmPort}: {route: string; llmPort?: LlmSettingsPort}) {
  const {t, preference, setPreference, systemLocale} = useI18n();
  const tab = settingsTab(route);
  const followName = languageName(languageFromSystemLocale(systemLocale));
  const languageNotRecorded = t("glossary.languageNotRecorded");
  return (
    <div className="settings-screen" data-testid="settings-page" data-has-aside="false">
      <header className="settings-chrome" data-testid="settings-chrome">
        <h1 className="settings-title"><I18nText k="nav.settings" /></h1>
        <nav className="settings-tabs" aria-label={t("nav.settings")}>
          <a
            href="#/settings/data"
            className={tab === "data" ? "active" : ""}
            data-testid="settings-tab-data"
          >
            <I18nText k="settings.tabs.data" />
          </a>
          <a
            href="#/settings/llm"
            className={tab === "llm" ? "active" : ""}
            data-testid="settings-tab-llm"
          >
            <I18nText k="settings.tabs.llm" />
          </a>
          <a
            href="#/settings/general"
            className={tab === "general" ? "active" : ""}
            data-testid="settings-tab-general"
            aria-current={tab === "general" ? "page" : undefined}
          >
            <I18nText k="settings.tabs.general" />
          </a>
        </nav>
      </header>
      <div className="settings-body" data-testid="settings-body">
        {tab === "general" ? (
          <div className="settings-general" data-testid="settings-general">
            <section className="settings-card" aria-labelledby="ui-language-title">
              <h2 id="ui-language-title"><I18nText k="settings.general.title" /></h2>
              <p><I18nText k="settings.general.immediate" /></p>
              <div className="settings-options" role="radiogroup" aria-labelledby="ui-language-title" data-option-count="3">
                <LanguageOption
                  value="system"
                  checked={preference === "system"}
                  title={<I18nText k="settings.general.followSystem" params={{languageName: followName}} />}
                  hint={<I18nText k="settings.general.followHint" />}
                  badge={preference === "system" ? <I18nText k="settings.general.defaultBadge" /> : undefined}
                  onSelect={setPreference}
                />
                <LanguageOption
                  value="zh"
                  checked={preference === "zh"}
                  title={<I18nText k="settings.general.optionZh" />}
                  badge={preference === "zh" ? <I18nText k="settings.general.defaultBadge" /> : undefined}
                  onSelect={setPreference}
                />
                <LanguageOption
                  value="en"
                  checked={preference === "en"}
                  title={<I18nText k="settings.general.optionEn" />}
                  badge={preference === "en" ? <I18nText k="settings.general.defaultBadge" /> : undefined}
                  onSelect={setPreference}
                />
              </div>
              <p><I18nText k="settings.general.ruleSystem" /></p>
              <p><I18nText k="settings.general.ruleManual" /></p>
              <p><I18nText k="settings.general.stored" /></p>
            </section>
            <section className="settings-card" aria-labelledby="about-title" data-testid="about-card">
              <h2 id="about-title"><I18nText k="settings.about.title" /></h2>
              <p data-testid="about-version">{t("settings.about.version", {version: appVersion})}</p>
              <p data-testid="about-sha">{t("settings.about.commit", {sha: gitSha})}</p>
            </section>
            <section className="settings-card" aria-labelledby="ui-language-scope">
              <h2 id="ui-language-scope"><I18nText k="settings.scope.title" /></h2>
              <div className="settings-scope-grid" data-testid="settings-scope-columns" data-scope-columns="2">
                <div data-scope-col="switches">
                  <p className="settings-scope-label"><I18nText k="settings.scope.switchesLabel" /></p>
                  <ul>
                    <li><I18nText k="settings.scope.switchUi" /></li>
                    <li><I18nText k="settings.scope.switchPages" /></li>
                    <li><I18nText k="settings.scope.switchNames" /></li>
                    <li><I18nText k="settings.scope.switchErrors" /></li>
                    <li><I18nText k="settings.scope.switchExport" /></li>
                    <li><I18nText k="settings.scope.switchLlm" /></li>
                  </ul>
                </div>
                <div data-scope-col="stays">
                  <p className="settings-scope-label"><I18nText k="settings.scope.keepsLabel" /></p>
                  <ul>
                    <li><I18nText k="settings.scope.keepNotes" /></li>
                    <li><I18nText k="settings.scope.keepSaved" /></li>
                    <li><I18nText k="settings.scope.keepLiterature" /></li>
                    <li><I18nText k="settings.scope.keepNames" /></li>
                    <li><I18nText k="settings.scope.keepLegacy" params={{languageNotRecorded}} /></li>
                  </ul>
                </div>
              </div>
              <p>
                <I18nText
                  k="settings.scope.footnote"
                  params={{
                    datePattern: t("format.datePattern"),
                    dateTimePattern: t("format.dateTimePattern"),
                  }}
                />
              </p>
            </section>
          </div>
        ) : tab === "llm" ? (
          <LlmSettingsCard port={llmPort} />
        ) : (
          <DataSourcesCard />
        )}
      </div>
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
  title: ReactNode;
  hint?: ReactNode;
  badge?: ReactNode;
  onSelect: (preference: UiLanguagePreference) => Promise<void>;
}) {
  return (
    <label
      className={`settings-option${checked ? " selected" : ""}`}
      data-testid={`ui-language-option-${value}`}
    >
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
      {badge ? <span className="settings-badge" aria-hidden="true">{badge}</span> : null}
    </label>
  );
}
