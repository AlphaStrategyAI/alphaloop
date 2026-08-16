import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

/**
 * Keyboard shortcuts for the v0.7.2 WebUI (R-Polish Story 9).
 *
 * Bindings (global, ignored when typing in an <input>):
 *   1 → /                          (Top-5)
 *   2 → /run/<rid>                 (Diagnostics)
 *   3 → /replay/<rid>              (Replay DAG)
 *   4 → /strategy/<sid>?rid=<rid>  (Strategy Detail)
 *   r → POST /api/runs/<rid>/replay (Rerun, with confirm)
 *   ? → toggle help overlay
 *   Esc → close any modal
 *
 * The hook returns nothing; consumers compose it with their own
 * confirm + help-overlay UI.  To avoid coupling the hook to a
 * specific UI, we expose `onRerun` and `onToggleHelp` callbacks.
 */
export interface ShortcutCallbacks {
  onRerun?: (rid: string) => void;
  onToggleHelp?: () => void;
}

export function useKeyboardShortcuts(callbacks: ShortcutCallbacks = {}) {
  const navigate = useNavigate();
  const params = useParams();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore typing in inputs / textareas / contenteditable.
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          target.isContentEditable
        ) {
          return;
        }
      }

      // Modifier-free single keys only.
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const key = e.key;
      const rid = (params as Record<string, string | undefined>).rid;

      switch (key) {
        case "1":
          e.preventDefault();
          navigate("/");
          break;
        case "2":
          if (rid) {
            e.preventDefault();
            navigate(`/run/${rid}`);
          } else {
            // No active run; pick the first available via fallback /.
            e.preventDefault();
            navigate("/");
          }
          break;
        case "3":
          if (rid) {
            e.preventDefault();
            navigate(`/replay/${rid}`);
          }
          break;
        case "4":
          if (rid) {
            e.preventDefault();
            navigate(`/strategy/_top?rid=${rid}`);
          }
          break;
        case "r":
        case "R":
          if (rid && callbacks.onRerun) {
            e.preventDefault();
            callbacks.onRerun(rid);
          }
          break;
        case "?":
          if (callbacks.onToggleHelp) {
            e.preventDefault();
            callbacks.onToggleHelp();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate, params, callbacks]);
}

export const KEYBOARD_SHORTCUTS: Array<{ key: string; label: string }> = [
  { key: "1", label: "Top-5 view" },
  { key: "2", label: "Run diagnostics" },
  { key: "3", label: "Replay DAG" },
  { key: "4", label: "Strategy detail" },
  { key: "r", label: "Rerun (with confirm)" },
  { key: "?", label: "Show this help" },
  { key: "Esc", label: "Close any modal" },
];
