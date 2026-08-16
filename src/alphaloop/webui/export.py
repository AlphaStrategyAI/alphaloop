"""Self-contained HTML export for v0.7.1 WebUI.

The frontend exposes /api/runs/<rid>/export which returns a single
self-contained .html file. The user can drop it into any browser
without a dev server — everything (CSS, JSON data, JS) is inlined.

This implementation produces a lightweight static snapshot: the
Quant Lab CSS tokens, a top-5 summary table, and a 3-axis radar
inline-rendered with SVG. It does NOT embed a full React runtime
(that would inflate the file > 500 KB); instead, it produces a
readable, shareable snapshot of the run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

QUANT_LAB_CSS = """
:root {
  --color-math: #5b6cff; --color-stats: #10b981; --color-ai: #f59e0b;
  --bg-0: #0b0e14; --bg-1: #11151d; --bg-2: #1a1f2b;
  --fg-0: #e5e9f0; --fg-1: #9ba3b4; --fg-2: #5c6573;
  --border: #2a3142;
  --font-mono: "JetBrains Mono", "SF Mono", "Consolas", monospace;
}
* { box-sizing: border-box; }
body { background: var(--bg-0); color: var(--fg-0); font-family: var(--font-mono);
       margin: 0; padding: 32px; line-height: 1.5; }
h1 { color: var(--fg-0); font-size: 24px; margin: 0 0 8px; }
h2 { color: var(--fg-0); font-size: 16px; margin: 24px 0 12px; }
.card { background: var(--bg-1); border: 1px solid var(--border);
        border-radius: 10px; padding: 16px 24px; margin-bottom: 16px; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { color: var(--fg-1); font-size: 12px; font-weight: normal; }
td { color: var(--fg-0); font-size: 13px; }
.metric { font-variant-numeric: tabular-nums; }
.math { color: var(--color-math); }
.stats { color: var(--color-stats); }
.ai { color: var(--color-ai); }
.pass { color: var(--color-stats); }
.warn { color: var(--color-ai); }
"""


def render_svg_radar(radar: list[dict[str, Any]], size: int = 320) -> str:
    """Render a 3-axis (per category) radar as static SVG."""
    if not radar:
        return "<svg width='320' height='320'></svg>"
    cx, cy = size / 2, size / 2
    r = size / 2 - 30
    n = len(radar)
    import math as _math

    def point(i: int, value: float) -> tuple[float, float]:
        angle = -_math.pi / 2 + 2 * _math.pi * i / n
        return (cx + _math.cos(angle) * r * value, cy + _math.sin(angle) * r * value)

    # Grid rings (0.25, 0.5, 0.75, 1.0)
    rings = []
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = [point(i, level) for i in range(n)]
        rings.append(
            f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" '
            'fill="none" stroke="#2a3142" stroke-width="1"/>'
        )
    # Axes
    axes = []
    for i in range(n):
        x, y = point(i, 1.0)
        axes.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            'stroke="#2a3142" stroke-width="1"/>'
        )
    # Data polygon
    data_pts = [point(i, max(0.0, min(1.0, p.get("value", 0.0)))) for i, p in enumerate(radar)]
    polygon = (
        f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)}" '
        'fill="rgba(91,108,255,0.2)" stroke="#5b6cff" stroke-width="2"/>'
    )
    # Labels
    labels = []
    for i, p in enumerate(radar):
        x, y = point(i, 1.15)
        anchor = "middle"
        if x < cx - 5:
            anchor = "end"
        elif x > cx + 5:
            anchor = "start"
        labels.append(
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'fill="#e5e9f0" font-size="11" font-family="JetBrains Mono">{p["axis"]}</text>'
        )
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        + "".join(rings)
        + "".join(axes)
        + polygon
        + "".join(labels)
        + "</svg>"
    )


def build_export_html(
    rid: str,
    top5_payload: dict[str, Any],
    diagnostics_payload: dict[str, Any],
) -> str:
    """Produce a self-contained HTML file."""
    top5 = top5_payload.get("top5", [])
    radar = diagnostics_payload.get("radar", [])
    manifest = diagnostics_payload.get("manifest", {})

    rows = []
    for p in top5:
        rows.append(
            f"<tr>"
            f"<td>#{p.get('rank', '?')}</td>"
            f"<td><code>{p.get('task_id', '')[:8]}</code></td>"
            f"<td>{p.get('strategy', '')}</td>"
            f'<td class="metric math">{p.get("dsr", 0):.3f}</td>'
            f'<td class="metric stats">{p.get("sharpe", 0):.3f}</td>'
            f'<td class="metric stats">{p.get("cagr", 0):.3%}</td>'
            f'<td class="metric stats">{p.get("max_dd", 0):.2%}</td>'
            f'<td class="{"pass" if p.get("passes_all") else "warn"}">'
            f'{"✓" if p.get("passes_all") else "⚠"}</td>'
            f"</tr>"
        )

    radar_svg = render_svg_radar(radar)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>alphaloop run {rid}</title>
<style>{QUANT_LAB_CSS}</style>
</head>
<body>
  <h1>alphaloop run <code>{rid}</code></h1>
  <p style="color: var(--fg-1); font-size: 13px;">
    Goal: {manifest.get("goal", "")} ·
    Seed: {manifest.get("seed", "")} ·
    Model: {manifest.get("llm_model", "")} ·
    Termination: {manifest.get("termination_reason", "?")}
  </p>

  <div class="card">
    <h2>Top 5 picks</h2>
    <table>
      <thead>
        <tr>
          <th>Rank</th><th>Task</th><th>Strategy</th>
          <th>DSR</th><th>Sharpe</th><th>CAGR</th><th>MaxDD</th><th>Pass</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows) if rows else '<tr><td colspan="8">No picks</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Q1–Q7 pass-rate radar</h2>
    {radar_svg}
  </div>

  <p style="color: var(--fg-2); font-size: 11px; margin-top: 32px;">
    Generated by alphaloop v0.7.1 WebUI export.
    Self-contained: no external network required.
  </p>
</body>
</html>
"""
