import type {DesktopView} from "./contracts";

/** Rail / main / aside numbers from the v0.9.3 uplift grid. */
export const RAIL_WIDTH = 72;
export const ASIDE_WIDTH = 320;
export const MAIN_MIN_WIDTH = 720;

function isSettingsRoute(route: string): boolean {
  return route === "#/settings" || route.startsWith("#/settings/") || route.startsWith("#/settings?");
}

/**
 * Aside 320 exists only on research detail (running, paused, completed) and draft.
 * List, glossary, and settings stay rail + main.
 */
export function shellHasAside(route: string, kind: DesktopView["kind"]): boolean {
  if (isSettingsRoute(route)) return false;
  if (route.startsWith("#/glossary") || route.startsWith("#/methods")) return false;
  if (route === "#/research" || route.startsWith("#/research?")) return false;
  return kind === "draft" || kind === "running" || kind === "completed";
}
