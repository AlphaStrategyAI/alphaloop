import {invoke} from "@tauri-apps/api/core";

import {resolveUiLanguage} from "./locale";
import type {Locale, UiLanguagePreference, UiLanguageSnapshot} from "./types";

export interface UiLanguagePort {
  load(): Promise<UiLanguageSnapshot>;
  save(preference: UiLanguagePreference): Promise<UiLanguageSnapshot>;
  readSystemLocale(): Promise<string | null>;
  setEngineLocale(locale: Locale): Promise<void>;
}

export function createMemoryLanguagePort(options?: {
  preference?: UiLanguagePreference;
  systemLocale?: string | null;
}): UiLanguagePort & {
  setSystemLocale: (tag: string | null) => void;
  engineLocales: Locale[];
} {
  let preference: UiLanguagePreference = options?.preference ?? "system";
  let systemLocale = options?.systemLocale ?? null;
  const engineLocales: Locale[] = [];
  const snapshot = (): UiLanguageSnapshot => ({
    preference,
    systemLocale,
    resolved: resolveUiLanguage(preference, systemLocale),
  });
  return {
    engineLocales,
    setSystemLocale(tag: string | null) {
      systemLocale = tag;
    },
    async load() {
      return snapshot();
    },
    async save(next: UiLanguagePreference) {
      preference = next;
      return snapshot();
    },
    async readSystemLocale() {
      return systemLocale;
    },
    async setEngineLocale(locale: Locale) {
      engineLocales.push(locale);
    },
  };
}

export const tauriLanguagePort: UiLanguagePort = {
  load: () => invoke<UiLanguageSnapshot>("get_ui_language"),
  save: (preference) => invoke<UiLanguageSnapshot>("set_ui_language", {preference}),
  readSystemLocale: () => invoke<string | null>("read_system_locale"),
  setEngineLocale: (locale) => invoke("set_engine_locale", {locale}),
};
