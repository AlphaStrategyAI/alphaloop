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

function isCount(value: string | number): boolean {
  if (typeof value === "number") return Number.isFinite(value);
  return /^\d+(?:\.\d+)?$/.test(value);
}

/** English uses `one` only for 1. Zero and every other count use `other`. Chinese does not branch. */
export function pluralCategory(locale: Locale, value: string | number): "one" | "other" {
  if (locale === "en" && Number(value) === 1) return "one";
  return "other";
}

type PluralBlock = {
  end: number;
  name: string;
  branches: Partial<Record<"one" | "other", string>>;
};

function parsePluralBlock(template: string, open: number): PluralBlock | null {
  const head = /^\{\{\s*([A-Za-z0-9_]+)\s*,\s*plural\s*,/.exec(template.slice(open));
  if (!head) return null;
  let index = open + head[0].length;
  const branches: PluralBlock["branches"] = {};
  while (index < template.length) {
    while (template[index] === " " || template[index] === "\n") index += 1;
    if (template.startsWith("}}", index)) {
      return {end: index + 2, name: head[1], branches};
    }
    const category = /^(one|other)\s*\{/.exec(template.slice(index));
    if (!category) return null;
    index += category[0].length;
    let depth = 1;
    const start = index;
    while (index < template.length && depth > 0) {
      const char = template[index];
      if (char === "{") depth += 1;
      else if (char === "}") depth -= 1;
      if (depth > 0) index += 1;
    }
    if (depth !== 0) return null;
    branches[category[1] as "one" | "other"] = template.slice(start, index);
    index += 1;
  }
  return null;
}

/**
 * ICU-style plural blocks: `{{name, plural, one {# item} other {# items}}}`.
 * `#` is the count. A branch may still contain `{{placeholders}}`.
 */
export function applyPlurals(template: string, params: MessageParams | undefined, locale: Locale): string {
  let out = "";
  let index = 0;
  while (index < template.length) {
    const open = template.indexOf("{{", index);
    if (open < 0) {
      out += template.slice(index);
      break;
    }
    out += template.slice(index, open);
    const block = parsePluralBlock(template, open);
    if (!block) {
      out += "{{";
      index = open + 2;
      continue;
    }
    const value = params?.[block.name];
    if (value === undefined || !isCount(value)) {
      out += template.slice(open, block.end);
      index = block.end;
      continue;
    }
    const category = pluralCategory(locale, value);
    const branch = block.branches[category] ?? block.branches.other ?? block.branches.one ?? "";
    out += branch.replace(/(?<![A-Za-z0-9_])#(?![A-Za-z0-9_])/g, String(value));
    index = block.end;
  }
  return out;
}

export function interpolate(template: string, params?: MessageParams, locale: Locale = "en"): string {
  const expanded = applyPlurals(template, params, locale);
  if (!params) return expanded;
  return expanded.replace(/\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g, (match, name: string) => {
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
  const rendered = interpolate(template, params, locale);
  if (rendered === key) return HARD_FALLBACK[locale];
  return rendered;
}
