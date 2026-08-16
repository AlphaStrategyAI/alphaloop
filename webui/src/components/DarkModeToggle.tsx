import { useEffect, useState } from "react";

/**
 * Dark/light theme toggle for the v0.7.2 WebUI (R-Polish Story 8).
 *
 * Behavior (per PRD § R-Polish):
 *  - Default: dark (Quant Lab).
 *  - Persists choice to localStorage["alphaloop.theme"].
 *  - Honors `prefers-color-scheme: light` on first visit (no stored
 *    choice yet).
 *  - Toggles `data-theme="light"` on <html>; CSS rules under
 *    `:root[data-theme="light"]` override the dark defaults.
 *  - Accessibility: high-contrast / reduced-motion users keep the
 *    dark default (their OS preference is already authoritative).
 */
const STORAGE_KEY = "alphaloop.theme";

function readInitialTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light") return stored;
  // First visit: honor OS preference, default dark.
  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => readInitialTheme());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // localStorage may be unavailable (e.g. SSR / private mode).
    }
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return { theme, toggle, setTheme };
}

export default function DarkModeToggle() {
  const { theme, toggle } = useTheme();

  return (
    <button
      data-testid="dark-mode-toggle"
      onClick={toggle}
      className="btn"
      title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      aria-label="Toggle dark mode"
      style={{ minWidth: 40 }}
    >
      <span aria-hidden>{theme === "dark" ? "🌙" : "☀"}</span>
    </button>
  );
}
