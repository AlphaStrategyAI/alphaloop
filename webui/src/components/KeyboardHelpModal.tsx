import { useEffect } from "react";
import { KEYBOARD_SHORTCUTS } from "../hooks/useKeyboardShortcuts";

/**
 * Modal help overlay listing the v0.7.2 keyboard shortcuts (Story 9).
 *
 * Closes on Esc or backdrop click.
 */
export default function KeyboardHelpModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      data-testid="keyboard-help-modal"
      role="dialog"
      aria-label="Keyboard shortcuts"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--r-lg)",
          padding: "var(--s-5) var(--s-6)",
          maxWidth: 480,
          width: "100%",
          color: "var(--fg-0)",
          fontFamily: "var(--font-mono)",
          boxShadow: "var(--shadow-2)",
        }}
      >
        <h2
          style={{
            fontSize: "var(--fs-xl)",
            margin: "0 0 var(--s-4)",
            color: "var(--color-math)",
          }}
        >
          Keyboard shortcuts
        </h2>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {KEYBOARD_SHORTCUTS.map((s) => (
              <tr key={s.key}>
                <td
                  style={{
                    padding: "var(--s-2) 0",
                    borderBottom: "1px solid var(--border)",
                    width: 80,
                  }}
                >
                  <kbd
                    style={{
                      background: "var(--bg-2)",
                      border: "1px solid var(--border)",
                      borderRadius: 4,
                      padding: "2px 8px",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--fs-sm)",
                      color: "var(--color-math)",
                    }}
                  >
                    {s.key}
                  </kbd>
                </td>
                <td
                  style={{
                    padding: "var(--s-2) 0",
                    borderBottom: "1px solid var(--border)",
                    color: "var(--fg-0)",
                    fontSize: "var(--fs-sm)",
                  }}
                >
                  {s.label}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p
          style={{
            color: "var(--fg-2)",
            fontSize: "var(--fs-xs)",
            marginTop: "var(--s-4)",
          }}
        >
          Press <kbd>Esc</kbd> or click outside to close.
        </p>
      </div>
    </div>
  );
}
