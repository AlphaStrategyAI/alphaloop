# WebUI

The alphaloop WebUI is a **Vite + React + TypeScript + Tailwind** SPA
that ships in `webui/`.  It runs alongside the FastAPI JSON backend
(`src/alphaloop/webui/api.py`) and consumes the same `runs/<rid>/`
artifacts that the CLI writes.

## Views

The WebUI has **4 views** (no new views in v0.7.2):

| View | Route | Purpose |
|------|-------|---------|
| Top-5            | `/`                  | Ranked list of strategies, with share + screenshot |
| Run diagnostics  | `/run/:rid`          | Q1–Q7 radar + manifest + pass-rate bar |
| Replay DAG       | `/replay/:rid`       | 6-node DAG + per-node timing |
| Strategy detail  | `/strategy/:sid`     | Equity curve + per-metric breakdown |

A 5th **share view** lives at `/s/:token` (v0.7.2) and renders a
self-contained HTML snapshot of a top-5 + diagnostics for a token
that was minted via `POST /api/runs/<rid>/share`. The view is
intentionally **read-only** — no rerun, no edit, no share-of-share.

## Animations

8 Framer Motion animations are reused across the views (no new
animations in v0.7.2):

1. `cardStagger` — top-5 cards cascade in
2. `hoverReveal` — additional metrics reveal on hover
3. `rollUpNumber` — DSR / Sharpe numbers count up
4. `radarDraw` — diagnostics radar sweeps in
5. `nodePulse` — DAG nodes pulse on the replay view
6. `edgeFlow` — DAG edges animate direction of data flow
7. `progressFill` — bars fill with spring physics
8. `successFlash` — pass-gate chips flash green

## Visual design

The "**Quant Lab**" dark theme is the default. The v0.7.2 light theme
overrides the CSS variables under `:root[data-theme="light"]` and is
toggled via the sun/moon button in the top-right corner.

The 3-color palette:

| Token | Dark | Light |
|-------|------|-------|
| `--color-math` | `#5b6cff` indigo | `#4a5be8` indigo |
| `--color-stats` | `#10b981` emerald | `#059669` emerald |
| `--color-ai` | `#f59e0b` amber | `#d97706` amber |

## Keyboard shortcuts

Press `?` to see the in-app overlay. The bindings:

| Key | Action |
|-----|--------|
| `1` | Top-5 view |
| `2` | Run diagnostics |
| `3` | Replay DAG |
| `4` | Strategy detail |
| `r` | Rerun (with confirm) |
| `?` | Toggle help |
| `Esc` | Close any modal |

The shortcuts are ignored when an `<input>` / `<textarea>` has
focus.

## Share link

Click **🔗 Share** on the Top-5 view. The frontend POSTs to
`/api/runs/<rid>/share`, gets back a token + URL, copies the URL to
the clipboard, and shows a toast. The URL has the form
`http://127.0.0.1:<port>/s/<token>` and resolves to a self-contained
HTML snapshot. Default TTL: 90 days. The token is a UUID4 + secrets
suffix (40 hex chars) — unguessable.

## Screenshot

Click **📷 PNG** on any view. The current `<main>` is rasterized to a
PNG and a download is triggered with the filename
`alphaloop-<view>-<rid>-<ts>.png`. The export uses an in-browser
SVG-rasterize fallback so it works without the (large) `html2canvas`
dependency.

## Bundle size

Total JS gzipped: **≤ 260 KB** (v0.7.2 budget, was 220 KB in v0.7.1).
The +40 KB is the share-link UI; the in-browser screenshot path uses
no external dependency.

## Performance

First Contentful Paint on the entry route: < 1.5 s on a laptop with
the dev server warm.

## Source layout

```
webui/
├── src/
│   ├── App.tsx                     # routes + global shortcuts + theme toggle
│   ├── main.tsx
│   ├── views/                      # TopFiveView, StrategyDetailView, ...
│   ├── components/                 # TopFiveCard, RadarChart, ...
│   ├── animations/                 # 8 Framer Motion presets
│   ├── hooks/                      # useKeyboardShortcuts
│   ├── api/                        # axios client
│   ├── styles/                     # quant-lab.css (dark + light)
│   └── tests/                      # Vitest + RTL
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── package.json
```
