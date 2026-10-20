import type {Locale, UiLanguagePreference} from "./types";

export type {Locale, UiLanguagePreference} from "./types";

/** zh and zh-* (POSIX zh_TW.UTF-8 included) are Chinese. Missing or anything else is English. */
export function languageFromSystemLocale(tag: string | null | undefined): Locale {
  if (tag == null) return "en";
  const text = tag.trim();
  if (!text) return "en";
  const primary = text.split(".")[0]?.split("@")[0] ?? "";
  const lang = primary.replaceAll("-", "_").split("_")[0]?.toLowerCase() ?? "";
  return lang === "zh" ? "zh" : "en";
}

export function normalizePreference(value: unknown): UiLanguagePreference {
  if (value === "system" || value === "zh" || value === "en") return value;
  return "system";
}

export function resolveUiLanguage(
  preference: unknown,
  systemLocale: string | null | undefined,
): Locale {
  const chosen = normalizePreference(preference);
  if (chosen === "zh" || chosen === "en") return chosen;
  return languageFromSystemLocale(systemLocale);
}

/** Names that never change with the interface language. */
export function languageName(locale: Locale): "中文" | "English" {
  return locale === "zh" ? "中文" : "English";
}
