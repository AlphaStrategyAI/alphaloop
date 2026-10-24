import type {MessageKey} from "./i18n/I18nProvider";
import type {MessageParams} from "./i18n/translate";

type Translate = (key: MessageKey, params?: MessageParams) => string;

/**
 * Human durations in the active language.
 * 7 seconds, 5 min, 1 h 30 min, 4 h. Never a decimal hour such as 0.00 or 0.0833333.
 */
export function formatDuration(seconds: number, t: Translate): string {
  const whole = Math.max(0, Math.round(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  if (hours > 0) {
    if (minutes === 0) return t("ui.copy.durationHours", {n: hours});
    return t("ui.copy.durationHoursMinutes", {hours, minutes});
  }
  if (minutes > 0) {
    if (secs === 0) return t("ui.copy.durationMinutesOnly", {n: minutes});
    return t("ui.copy.durationMinutes", {minutes, seconds: secs});
  }
  return t("ui.copy.durationSeconds", {n: secs});
}

/** Parse an engine duration label. Returns null when the text is not a duration. */
export function formatEngineDuration(text: string, t: Translate): string | null {
  const trimmed = text.trim();
  const hours = /^(\d+(?:\.\d+)?)\s*小时$/.exec(trimmed) ?? /^(\d+(?:\.\d+)?)h$/i.exec(trimmed); // i18n-allow engine duration text
  if (hours) return formatDuration(Number(hours[1]) * 3600, t);
  const clock = /^(\d+)h(\d+)$/i.exec(trimmed);
  if (clock) return formatDuration(Number(clock[1]) * 3600 + Number(clock[2]) * 60, t);
  const seconds = /^(\d+)\s*秒$/.exec(trimmed); // i18n-allow engine duration text
  if (seconds) return formatDuration(Number(seconds[1]), t);
  const minutes = /^(\d+)\s*分\s*(\d+)\s*秒$/.exec(trimmed); // i18n-allow engine duration text
  if (minutes) return formatDuration(Number(minutes[1]) * 60 + Number(minutes[2]), t);
  return null;
}
