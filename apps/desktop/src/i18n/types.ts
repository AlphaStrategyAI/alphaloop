export type Locale = "zh" | "en";

export type UiLanguagePreference = "system" | Locale;

export interface UiLanguageSnapshot {
  preference: UiLanguagePreference;
  systemLocale: string | null;
  resolved: Locale;
}
