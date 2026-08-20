# WebUI

The **first-release** morning UI is the packaged static page at
`src/alphaloop/webui/static/`, served by `alphaloop start` on loopback.
Fill the guided hypothesis form (or load the example, or paste YAML),
preview the compiled protocol (readable method grid, planned trial
count leading the preview card, seed, and budgets), then freeze it.
The signal list is grouped by economic family (trend, mean reversion,
relative value). The dataset file picker accepts parquet or a
wide close-only CSV. Per-symbol OHLCV is rejected. Load example uses designed secondary chrome
(not FOUND green). Preview protocol uses focus-blue chrome (not
FOUND green). Freeze and submit uses ink background and FOUND accent
chrome (not ad-hoc hex). Ctrl/Cmd+Enter previews, then freezes. j/k or arrows move between morning
jobs. Cancel or resume from the job detail without
leaving the page. A human **Export .asb** click on a `FOUND` candidate
shows the same four-line receipt as `alphaloop export` (`FOUND`,
qualifying id, path, no-alpha) in the morning verdict cluster next to
the export button. Switching jobs clears a stale receipt. The verdict
Export control uses the same designed chrome as the qualifying list,
with FOUND accent color. The verdict Load into editor control uses the
same designed chrome as the queued list, with NO_EVIDENCE warn color
(not FOUND green). Leave the host awake, and review `FOUND` /
`NO_EVIDENCE` / `INCONCLUSIVE` in the morning — job cards show the
frozen statement and `n_trials`; the detail funnel shows how many
frozen trials were evaluated, passed, and failed. A running job card
and verdict pulse (focus blue, not FOUND green); the detail shows
`Worker heartbeat:` when the supervisor has a timestamp. A failed job
shows the stored worker error, recovery count, and Resume above the
report. **Replay report** rewrites `report.md` from sealed artifacts
without re-running gates or inventing FOUND. Cancel uses the same designed chrome as Export/Load with
focus-blue (running pulse), not FOUND green. Resume uses warn chrome
(failed recovery), not FOUND green. Job status and
research outcome stay separate. The page does not promise alpha.

The Vite + React + TypeScript Quant Lab SPA under `webui/` is **frozen
heritage**. It is not the overnight-lab product UI. The notes below
document that frozen tree only.

## Frozen Quant Lab SPA (heritage)

The heritage alphaloop WebUI is a **Vite + React + TypeScript + Tailwind**
SPA bundled into the package at `webui/`. It was designed to run
alongside the FastAPI JSON backend (`src/alphaloop/webui/api.py`) and
read the same `runs/<rid>/` artifacts that the CLI writes.

## Layout — the 4 views

The app opens on **Top-5**.  Keyboard `1`–`4` jump between views.

| # | View          | Route              | What it shows |
|---|---------------|--------------------|---------------|
| 1 | **Top-5**         | `/`                | Ranked list, each card with DSR / Sharpe / drawdown.  Share & screenshot in the top-right. |
| 2 | **Run diagnostics** | `/run/:rid`      | Q1–Q6 radar + manifest panel + per-gate pass-rate bar. |
| 3 | **Replay DAG**    | `/replay/:rid`     | 6-node DAG animated from `progress.json` + per-node timing. |
| 4 | **Strategy detail** | `/strategy/:sid` | Equity curve + per-metric breakdown + tickers & weight timeline. |

A 5th **share view** at `/s/:token` (v0.7.2) renders a self-contained
read-only snapshot of the top-5 + diagnostics.  No rerun, no edit,
no share-of-share.

## The 8 animations

All 8 are **Framer Motion** presets in `webui/src/animations/`.  They
are reused across views — no new animations were added in v0.7.2, only
the dark/light polish + keyboard + screenshot pass.

1. **`cardStagger`** — top-5 cards cascade in on mount.
2. **`hoverReveal`** — additional metrics slide in on card hover.
3. **`rollUpNumber`** — DSR / Sharpe / max-DD numbers count up on first paint.
4. **`radarDraw`** — diagnostics radar sweeps in along its 6 axes.
5. **`nodePulse`** — DAG nodes pulse on the replay view to show the active node.
6. **`edgeFlow`** — DAG edges animate in the direction of data flow.
7. **`progressFill`** — bars fill with spring physics (stiffness 120, damping 16).
8. **`successFlash`** — pass-gate chips flash emerald for 600 ms when a gate flips.

## The Quant Lab palette

The "**Quant Lab**" dark theme is the default (matches the MkDocs
palette).  The v0.7.2 light theme overrides the CSS variables under
`:root[data-theme="light"]` and is toggled via the 🌙 / ☀ button in
the top-right.

3 functional colors, each with a meaning — never decorative:

| Token         | Color (dark) | Color (light) | Meaning |
|---------------|--------------|---------------|---------|
| `--color-math`  | `#5b6cff` indigo | `#4a5be8` indigo | **Deterministic / numeric** — backtest metrics, equity curves, radar. |
| `--color-stats` | `#10b981` emerald | `#059669` emerald | **Passed gates** — success chips, healthy diagnostics. |
| `--color-ai`    | `#f59e0b` amber | `#d97706` amber | **LLM-generated** — planner output, judge annotations, free-text notes. |

> Rule: when you see amber, ask *"is this from the LLM or from a
> number?"*  If you can't tell, the design is broken.

## Keyboard shortcuts

Press `?` anywhere for the in-app help overlay.

| Key       | Action |
|-----------|--------|
| `1`       | Top-5 view |
| `2`       | Run diagnostics |
| `3`       | Replay DAG |
| `4`       | Strategy detail |
| `r`       | Rerun (with confirm) |
| `?`       | Toggle help |
| `Esc`     | Close any modal |
| `d` / `l` | Toggle dark / light mode |

Shortcuts are ignored when an `<input>` or `<textarea>` has focus.

## Share link (v0.7.2)

Click **🔗 Share** on the Top-5 view.  The frontend POSTs to
`/api/runs/<rid>/share`, gets back a token + URL, copies the URL to
the clipboard, and shows a toast.  The URL has the form
`http://127.0.0.1:<port>/s/<token>` and renders a self-contained HTML
snapshot.  Default TTL: 90 days, max 365.  The token is a UUID4 +
secrets suffix (40 hex chars) — unguessable.

## Screenshot (v0.7.2)

Click **📷 PNG** on any view.  The current `<main>` is rasterized to a
PNG via an in-browser SVG-rasterize fallback (no `html2canvas`
dependency) and a download is triggered with the filename
`alphaloop-<view>-<rid>-<ts>.png`.

## Bundle & perf budget

- Total JS gzipped: **≤ 260 KB** (v0.7.2 budget, was 220 KB in v0.7.1).
  The +40 KB is the share-link UI; the in-browser screenshot path uses
  no external dependency.
- First Contentful Paint on the entry route: **< 1.5 s** on a laptop
  with the dev server warm.
