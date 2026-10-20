import type {ReactNode} from "react";

import {localizeError} from "./errors";
import {useI18n, type MessageKey} from "./I18nProvider";

const CONSTRUCTION_KEYS: Record<string, MessageKey> = {
  "单票 ≤5%、成本 5 bp（保守产品假设）": "confirm.construction.usEquityCap",
  "成本 5 bp（保守产品假设）": "confirm.construction.usEquityCost",
  "单票 ≤5%、成本 20 bp（保守产品假设）": "confirm.construction.cnEquityCap",
  "成本 20 bp（保守产品假设）": "confirm.construction.cnEquityCost",
  "基金腿不受单票 5% 上限约束、成本 1 bp（保守产品假设）": "confirm.construction.usFund",
  "基金腿不受单票 5% 上限约束、成本 5 bp（保守产品假设）": "confirm.construction.cnFund",
};

export function constructionNoticeKey(text: string): MessageKey | null {
  return CONSTRUCTION_KEYS[text] ?? null;
}

export function ConstructionNoticeText({text}: {text: string}): ReactNode {
  const {t} = useI18n();
  const key = constructionNoticeKey(text);
  return key ? t(key) : text;
}

export function ConfirmDataNoticeText({
  text,
  code,
  params,
}: {
  text: string;
  code?: string | null;
  params?: Record<string, string | number> | null;
}): ReactNode {
  const {resolved} = useI18n();
  if (!code) return text;
  return localizeError(resolved, {code, message: text, params}).summary;
}
