import {formatUiDateTime} from "./i18n/formatUiDateTime";

/**
 * Display-only clock: YYYY-MM-DD HH:mm in the computer's local zone.
 * Omit `timeZone` for the machine zone. Pass null when that zone cannot be read (UTC with Z).
 * Stored timestamps, fingerprints, and date-only trading days are not formatted here.
 */
export function formatResearchTimestamp(iso: string, timeZone?: string | null): string {
  return formatUiDateTime(iso, timeZone);
}
