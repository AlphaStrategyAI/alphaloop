import type {ReactNode} from "react";

import {isFinalMessageKey} from "./catalog";
import {useI18n, type MessageKey} from "./I18nProvider";
import type {MessageParams} from "./translate";
import "./placeholder.css";

export function isPlaceholderMessageKey(key: string): boolean {
  return !isFinalMessageKey(key);
}

export function I18nText({k, params}: {k: MessageKey; params?: MessageParams}): ReactNode {
  const {t, resolved} = useI18n();
  const text = t(k, params);
  if (resolved !== "en" || !isPlaceholderMessageKey(k)) return text;
  return (
    <span className="i18n-placeholder" data-i18n-placeholder="">
      {text}
    </span>
  );
}
