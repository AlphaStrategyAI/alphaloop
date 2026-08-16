import { useState } from "react";

/**
 * Screenshot button for the v0.7.2 WebUI (R-Polish Story 10).
 *
 * Renders the current `<main>` element (or a custom target) to a PNG
 * and triggers a browser download.  The implementation uses the
 * SVG-rasterize fallback path (no external html2canvas dependency) so
 * the button keeps working even when html2canvas is not bundled.
 *
 * Filename: alphaloop-<view>-<rid>-<ts>.png
 */
export interface ScreenshotButtonProps {
  rid?: string;
  view: string; // 'top5' | 'diagnostics' | 'replay' | 'strategy'
  targetRef?: React.RefObject<HTMLElement>;
}

function timestamp(): string {
  const d = new Date();
  return d
    .toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", "_")
    .replace("Z", "");
}

/**
 * Lightweight in-browser PNG screenshot of a DOM subtree.
 *
 * Strategy: serialize the element's HTML + inline styles into a
 * standalone SVG (foreignObject), draw it onto a <canvas>, then
 * export to PNG.  This works for simple layouts; complex CSS
 * (gradients, animations) may render slightly differently from a
 * real DOM render.
 */
async function capturePng(el: HTMLElement): Promise<Blob> {
  const w = Math.max(1, el.scrollWidth);
  const h = Math.max(1, el.scrollHeight);

  const escaped = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const clone = el.cloneNode(true) as HTMLElement;
  // Inline computed styles for the key nodes so the SVG renders
  // close to the original.  This is a best-effort fallback.
  const orig = el.querySelectorAll("*");
  const cl = clone.querySelectorAll("*");
  for (let i = 0; i < orig.length && i < cl.length; i++) {
    const cs = window.getComputedStyle(orig[i]);
    const props = [
      "color",
      "background",
      "background-color",
      "border",
      "border-radius",
      "padding",
      "margin",
      "font",
      "font-size",
      "font-family",
      "font-weight",
      "text-align",
    ];
    let style = "";
    for (const p of props) {
      const v = cs.getPropertyValue(p);
      if (v) style += `${p}:${v};`;
    }
    cl[i].setAttribute("style", style);
  }

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">` +
    `<foreignObject width="100%" height="100%">` +
    `<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:sans-serif;background:var(--bg-0);">` +
    escaped(clone.outerHTML) +
    `</div></foreignObject></svg>`;

  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  try {
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = (err) => reject(err);
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas 2d not available");
    ctx.fillStyle = "#0b0e14";
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((b) => {
        if (b) resolve(b);
        else reject(new Error("toBlob failed"));
      }, "image/png");
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function ScreenshotButton({
  rid,
  view,
  targetRef,
}: ScreenshotButtonProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onClick = async () => {
    setBusy(true);
    setError(null);
    try {
      // Default target: <main> if present, otherwise any element with
      // data-testid=<view>, otherwise document.body.
      const target =
        (targetRef?.current as HTMLElement | null) ||
        (document.querySelector("main") as HTMLElement | null) ||
        (document.querySelector(`[data-testid="${view}"]`) as HTMLElement | null) ||
        document.body;
      const blob = await capturePng(target);
      const filename = `alphaloop-${view}-${rid ?? "no-rid"}-${timestamp()}.png`;
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      data-testid="screenshot-button"
      onClick={onClick}
      disabled={busy}
      className="btn"
      title="Download view as PNG"
      aria-label="Download view as PNG"
    >
      {busy ? "Capturing…" : "📷 PNG"}
      {error && (
        <span
          role="alert"
          style={{ marginLeft: 8, color: "var(--color-ai)", fontSize: 11 }}
        >
          {error}
        </span>
      )}
    </button>
  );
}
