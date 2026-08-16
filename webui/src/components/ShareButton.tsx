import { useState } from "react";
import { apiClient } from "../api/client";

/**
 * Share button for the v0.7.2 WebUI (R-ShareLink Story 4).
 *
 * On click: POST /api/runs/<rid>/share, copy the URL to the
 * clipboard, show a toast.  Falls back to selecting the URL into
 * a textarea if the Clipboard API is unavailable (e.g. insecure
 * context).
 */
export default function ShareButton({ rid }: { rid: string }) {
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const onClick = async () => {
    setBusy(true);
    setToast(null);
    try {
      const resp = await apiClient.mintShareLink(rid);
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(resp.url);
          setToast(`Copied: ${resp.url}`);
        } else {
          setToast(`Share URL: ${resp.url}`);
        }
      } catch {
        setToast(`Share URL: ${resp.url}`);
      }
    } catch (e) {
      setToast(`Share failed: ${String(e)}`);
    } finally {
      setBusy(false);
      // Auto-dismiss toast after 4s.
      setTimeout(() => setToast(null), 4000);
    }
  };

  return (
    <span style={{ position: "relative", display: "inline-block" }}>
      <button
        data-testid="share-button"
        onClick={onClick}
        disabled={busy}
        className="btn"
        title="Generate a share link"
        aria-label="Share this run"
      >
        {busy ? "Sharing…" : "🔗 Share"}
      </button>
      {toast && (
        <span
          role="status"
          data-testid="share-toast"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            background: "var(--bg-2)",
            color: "var(--fg-0)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-sm)",
            padding: "var(--s-2) var(--s-3)",
            fontSize: "var(--fs-xs)",
            whiteSpace: "nowrap",
            zIndex: 10,
            boxShadow: "var(--shadow-2)",
          }}
        >
          {toast}
        </span>
      )}
    </span>
  );
}
