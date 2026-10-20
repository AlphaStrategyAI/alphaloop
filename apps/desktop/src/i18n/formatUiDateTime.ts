const CALENDAR_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Human-facing dates are YYYY-MM-DD. Timestamps are YYYY-MM-DD HH:mm±HH:mm
 * in the computer's local zone, in both languages.
 * Pass null when the zone cannot be read: the clock is UTC and ends with Z.
 * A calendar day is returned unchanged. It is not a UTC midnight timestamp.
 */
export function formatUiDateTime(input: Date | string | number, timeZone?: string | null): string {
  if (typeof input === "string" && CALENDAR_DATE.test(input)) {
    return input;
  }
  const date = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(date.getTime())) {
    throw new RangeError("invalid date");
  }
  const zone = timeZone === undefined ? readLocalTimeZone() : timeZone;
  if (zone === null) {
    return `${formatWallClock(date, "UTC")}Z`;
  }
  return `${formatWallClock(date, zone)}${numericOffset(date, zone)}`;
}

export function formatUiDate(input: Date | string | number, timeZone?: string | null): string {
  if (typeof input === "string" && CALENDAR_DATE.test(input)) {
    return input;
  }
  return formatUiDateTime(input, timeZone).slice(0, 10);
}

function readLocalTimeZone(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!zone) return null;
    new Intl.DateTimeFormat("en-US", {timeZone: zone}).format(0);
    return zone;
  } catch {
    return null;
  }
}

function formatWallClock(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  let hour = pick("hour");
  if (hour === "24") hour = "00";
  return `${pick("year")}-${pick("month")}-${pick("day")} ${hour}:${pick("minute")}`;
}

/** ICU longOffset is "GMT+08:00", "GMT-05:00", "GMT+05:30", or "GMT" for zero. */
function numericOffset(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZoneName: "longOffset",
  }).formatToParts(date);
  const name = parts.find((part) => part.type === "timeZoneName")?.value ?? "";
  const match = /^(?:GMT|UTC)([+-])(\d{1,2})(?::(\d{2}))?$/.exec(name);
  if (!match) {
    if (name === "GMT" || name === "UTC" || name === "GMT+00:00" || name === "UTC+00:00") {
      return "+00:00";
    }
    throw new RangeError(`unreadable offset: ${name}`);
  }
  const hours = match[2].padStart(2, "0");
  const minutes = (match[3] ?? "00").padStart(2, "0");
  return `${match[1]}${hours}:${minutes}`;
}
