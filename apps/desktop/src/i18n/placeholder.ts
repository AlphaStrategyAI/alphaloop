const LEGACY_PREFIX = "«i18n-placeholder»";

export function containsPlaceholderMarker(text: string): boolean {
  return text.includes(LEGACY_PREFIX);
}
