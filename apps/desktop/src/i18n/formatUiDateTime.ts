/**
 * Interface dates are YYYY-MM-DD, and timestamps YYYY-MM-DD HH:mm, in both languages.
 * `format.ts` still serves existing call sites until I1 switches them over.
 */
export function formatUiDateTime(input: Date | string | number, timeZone?: string): string {
  const date = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(date.getTime())) {
    throw new RangeError("invalid date");
  }
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

export function formatUiDate(input: Date | string | number, timeZone?: string): string {
  return formatUiDateTime(input, timeZone).slice(0, 10);
}
