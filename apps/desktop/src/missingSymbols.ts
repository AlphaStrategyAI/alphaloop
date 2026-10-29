import {enCatalog, zhCatalog} from "./i18n/catalog";

/** Stable engine code for a run that paused because no symbols were locked. */
export const EMPTY_SYMBOLS_CODE = "DATA_SYMBOLS_EMPTY";

function firstSentence(text: string): string {
  const cut = text.search(/[。.]/);
  if (cut < 0) return text;
  return text.slice(0, cut + 1);
}

/**
 * True when the engine reported DATA_SYMBOLS_EMPTY.
 * A payload that only has the stored message still matches the catalog sentence
 * (or its first sentence, which is the shorter classified form).
 */
export function missingSymbolsError(
  error: {code?: string; message?: string | null} | null | undefined,
): boolean {
  if (!error) return false;
  if (error.code === EMPTY_SYMBOLS_CODE) return true;
  const message = error.message?.trim() ?? "";
  if (!message) return false;
  const sentences = [
    zhCatalog.errors.codes.DATA_SYMBOLS_EMPTY,
    enCatalog.errors.codes.DATA_SYMBOLS_EMPTY,
  ];
  return sentences.some((text) => {
    const lead = firstSentence(text);
    return message === text || message === lead || message.includes(text) || (lead.length > 0 && message.includes(lead));
  });
}
