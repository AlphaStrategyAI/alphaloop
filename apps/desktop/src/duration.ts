import type {MessageKey} from "./i18n/I18nProvider";
import type {MessageParams} from "./i18n/translate";

type Translate = (key: MessageKey, params?: MessageParams) => string;

/** Sub-hour durations stay in minutes and seconds. Never "0.00 hours". */
export function formatDuration(seconds: number, t: Translate): string {
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 3600) {
    const minutes = Math.floor(whole / 60);
    const secs = whole % 60;
    if (minutes === 0) {
      return t("ui.copy.durationSeconds", {n: secs});
    }
    return t("ui.copy.durationMinutes", {minutes, seconds: secs});
  }
  return t("ui.copy.hours", {n: (seconds / 3600).toFixed(2)});
}
