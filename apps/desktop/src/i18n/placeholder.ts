import {PLACEHOLDER_MARKER} from "./conventions";

export function containsPlaceholderMarker(text: string): boolean {
  return text.includes(PLACEHOLDER_MARKER);
}
