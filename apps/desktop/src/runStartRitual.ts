import type {DesktopView} from "./contracts";

export const RUN_START_RITUAL_MS = 500;

export function shouldTriggerRunStartRitual(
  previous: DesktopView | undefined,
  next: DesktopView,
): boolean {
  if (!previous || previous.kind !== "confirm_run" || next.kind !== "running") {
    return false;
  }
  return previous.researchId === next.researchId;
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
