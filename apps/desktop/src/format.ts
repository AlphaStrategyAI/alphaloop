import {formatUiDateTime} from "./i18n/formatUiDateTime";

/**
 * Interface timestamps are YYYY-MM-DD HH:mm in every language.
 * The zone stays Asia/Shanghai: the settings spec fixes the shape, not the zone.
 */
export function formatResearchTimestamp(
  iso: string,
  timeZone: string = "Asia/Shanghai",
): string {
  return formatUiDateTime(iso, timeZone);
}
