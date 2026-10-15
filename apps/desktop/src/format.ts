/** Fixed timezone for deterministic vitest. */
export function formatResearchTimestamp(
  iso: string,
  timeZone: string = "Asia/Shanghai",
): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}
