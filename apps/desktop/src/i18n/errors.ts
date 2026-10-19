import {ERROR_CODES, type ErrorCode} from "./conventions";
import {enCatalog, zhCatalog} from "./catalog";
import {translate, type MessageParams} from "./translate";
import type {Locale} from "./types";

export interface ErrorInput {
  code?: string | null;
  message?: string | null;
  params?: MessageParams | null;
  detail?: string | null;
}

export interface LocalizedError {
  summary: string;
  next: string | null;
  detail: string | null;
  unmapped: boolean;
}

const KNOWN_CODES = new Set<string>(Object.keys(ERROR_CODES));

function hardFallback(locale: Locale): string {
  return locale === "zh" ? "（暂无对应文案）" : "Text unavailable.";
}

/**
 * Known codes use the catalog. Unknown codes use the generic explanation.
 * Technical detail is the raw engine text, not translated. Message keys are never shown.
 */
export function localizeError(locale: Locale, error: ErrorInput): LocalizedError {
  const code = error.code?.trim() || "";
  if (!code) {
    return {
      summary: error.message?.trim() || hardFallback(locale),
      next: null,
      detail: null,
      unmapped: false,
    };
  }
  if (!KNOWN_CODES.has(code)) {
    const raw = [error.detail, error.message].filter((part) => part && part.trim()).join("\n");
    return {
      summary: translate(locale, "errors.unmapped.summary", undefined, {zh: zhCatalog, en: enCatalog}),
      next: translate(locale, "errors.unmapped.next", undefined, {zh: zhCatalog, en: enCatalog}),
      detail: [`code: ${code}`, raw].filter((part) => part.trim()).join("\n"),
      unmapped: true,
    };
  }
  const key = `errors.codes.${code as ErrorCode}`;
  const detail = error.detail?.trim() ? error.detail : null;
  return {
    summary: translate(locale, key, error.params ?? undefined, {zh: zhCatalog, en: enCatalog}),
    next: null,
    detail,
    unmapped: false,
  };
}
