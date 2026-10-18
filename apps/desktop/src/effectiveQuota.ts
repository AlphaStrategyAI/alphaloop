/** Parse engine-provided effective quota strings like `3h12 / 12h` for UI meters only. */
export type EffectiveQuota = {usedLabel: string; totalLabel: string; ratio: number};

const PAIR = /^\s*(.+?)\s*\/\s*(.+?)\s*$/;

function parseHoursMinutes(token: string): number | null {
  const trimmed = token.trim();
  const hm = /^(\d+)\s*h\s*(\d+)?$/i.exec(trimmed.replace(/\s+/g, ""));
  if (hm) {
    const hours = Number(hm[1]);
    const minutes = hm[2] ? Number(hm[2]) : 0;
    return hours * 60 + minutes;
  }
  const decimal = /^(\d+(?:\.\d+)?)\s*h$/i.exec(trimmed);
  if (decimal) {
    return Math.round(Number(decimal[1]) * 60);
  }
  const zh = /^(\d+(?:\.\d+)?)\s*小时/.exec(trimmed);
  if (zh) {
    return Math.round(Number(zh[1]) * 60);
  }
  return null;
}

export function parseEffectiveQuota(effective?: string | null): EffectiveQuota | null {
  if (!effective) {
    return null;
  }
  const match = PAIR.exec(effective);
  if (!match) {
    return null;
  }
  const usedLabel = match[1].trim();
  const totalLabel = match[2].trim();
  const usedMin = parseHoursMinutes(usedLabel);
  const totalMin = parseHoursMinutes(totalLabel);
  if (usedMin == null || totalMin == null || totalMin <= 0) {
    return null;
  }
  const ratio = Math.min(1, Math.max(0, usedMin / totalMin));
  return {usedLabel, totalLabel, ratio};
}
