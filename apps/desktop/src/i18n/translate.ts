import {enCatalog, zhCatalog, type MessageCatalog} from "./catalog";
import type {Locale} from "./types";

export type MessageParams = Record<string, string | number>;

type Catalogs = {zh: MessageCatalog; en: MessageCatalog};

const HARD_FALLBACK: Record<Locale, string> = {
  zh: "（暂无对应文案）",
  en: "Text unavailable.",
};

export function lookupMessage(catalog: unknown, key: string): string | undefined {
  let current: unknown = catalog;
  for (const part of key.split(".")) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  if (typeof current !== "string" || current.trim() === "") return undefined;
  return current;
}

export function interpolate(template: string, params?: MessageParams): string {
  if (!params) return template;
  return template.replace(/\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g, (match, name: string) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}

/**
 * Missing keys fall back to the other language. The raw key is never returned.
 */
export function translate(
  locale: Locale,
  key: string,
  params?: MessageParams,
  catalogs: Catalogs = {zh: zhCatalog, en: enCatalog},
): string {
  const other: Locale = locale === "zh" ? "en" : "zh";
  const template =
    lookupMessage(catalogs[locale], key) ?? lookupMessage(catalogs[other], key);
  if (!template || template === key) return HARD_FALLBACK[locale];
  const rendered = interpolate(template, params);
  if (rendered === key) return HARD_FALLBACK[locale];
  return rendered;
}
