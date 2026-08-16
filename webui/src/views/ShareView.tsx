/**
 * Read-only snapshot view for /s/<token> (R-ShareLink Story 5).
 *
 * The backend already returns a self-contained HTML page at
 * GET /api/share/<token>.  This React route is a thin wrapper that
 * fetches the HTML and renders it in an iframe, so the share view
 * is truly decoupled from the SPA shell — no rerun, no edit, no
 * share-of-share.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

export default function ShareView() {
  const { token } = useParams<{ token: string }>();
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let aborted = false;
    fetch(`/api/share/${token}`)
      .then((r) => {
        if (!r.ok) {
          return r.text().then((t) => {
            throw new Error(
              r.status === 404
                ? "Share link not found"
                : r.status === 410
                ? "Share link expired or revoked"
                : `HTTP ${r.status}: ${t.slice(0, 120)}`,
            );
          });
        }
        return r.text();
      })
      .then((body) => {
        if (!aborted) setHtml(body);
      })
      .catch((e) => {
        if (!aborted) setError(String(e));
      });
    return () => {
      aborted = true;
    };
  }, [token]);

  if (error) {
    return (
      <div className="p-8">
        <div className="card max-w-2xl mx-auto text-center">
          <h2 className="text-xl text-fg-0 mb-2">Share link unavailable</h2>
          <p className="text-fg-1 text-sm" data-testid="share-error">
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (!html) {
    return (
      <div className="p-8">
        <div className="card max-w-2xl mx-auto text-center">
          <p className="text-fg-1 text-sm">Loading shared view…</p>
        </div>
      </div>
    );
  }

  return (
    <iframe
      data-testid="share-iframe"
      srcDoc={html}
      title="Shared alphaloop run"
      style={{
        width: "100%",
        height: "100vh",
        border: "none",
        background: "var(--bg-0)",
      }}
    />
  );
}
