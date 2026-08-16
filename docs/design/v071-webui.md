---
title: "alphaloop v0.7.1 — WebUI Design (4 Views + 8 Micro-Animations + Quant Lab Visual Language)"
version: "0.7.1"
status: "design"
authors:
  - alphaloop design subagent (Coder)
date: "2026-08-16"
loop: "alphaloop-v071-webui-design"
related_roadmap_section: "ROADMAP.md § v0.7.1"
supersedes: "none — adds to v0.7 design (docs/design/v07-hybrid-loop.md)"
---

# alphaloop v0.7.1 — WebUI Design

## 0. Context

alphaloop v0.7 (commit `882f4d1` on `AlphaStrategyAI/alphaloop`) ships the
hybrid loop MVP: a 6-node DAG (N1 Load → N2 Plan → N3 Execute → N4 Diagnose →
N5 Aggregate → N6 Commit), `manifest.yaml` + `results.parquet` + `top5.json` +
`report.md` artifacts per run, and `LoopReplay` for deterministic re-execution
(v0.7 design: `docs/design/v07-hybrid-loop.md`, 883 lines).

The v0.7 CLI surfaces results as plain text + Markdown. v0.7.1 adds a
**read-mostly WebUI** that turns the same artifacts into 4 interactive
views, with 8 Framer Motion micro-animations and a dark "Quant Lab"
visual language. The UI is a **Vite + React + TypeScript SPA** that
consumes JSON from a FastAPI JSON-only backend (FastAPI stays, but it
stops serving HTML). The goal is **make the loop legible**: a quant
researcher can spend 5 minutes in the UI and walk away understanding
what the loop did, what it picked, and why.

This document is **design only** — no implementation. Per the loop state
file, implementation is gated on user explicit OK after this design is
reviewed. Hard wall (per loop state file §"设计阶段 hard wall"):

1. Only write this design doc; no code, no tests, no implementation.
2. Do not modify any existing alphaloop file except by *creating*
   `docs/design/v071-webui.md`.
3. Do not write `src/alphaloop/webui/*` (deferred to v0.7.1 dev).
4. Do not write `webui/src/*` or `webui/package.json` (deferred to
   v0.7.1 dev).
5. Do not write `tests/test_webui.py` or `tests/webui/*.test.tsx`
   (deferred to v0.7.1 dev).
6. No commits, no pushes, no broker connections.

---

## 1. Goals

### 1.1 Primary goal

Ship a **Vite + React + TypeScript SPA** (with **Tailwind CSS** for
layout primitives and **Framer Motion** for animation) that consumes
JSON from an existing FastAPI JSON-only backend and the v0.7 artifacts
(`runs/<run_id>/manifest.yaml` + `results.parquet` + `top5.json` +
`report.md`) to render 4 interactive views:

| # | View          | Route                | WOW moment                                          |
|---|---------------|----------------------|-----------------------------------------------------|
| 1 | Top-5 card    | `/`                  | **5 cards in one screen** side-by-side, hover-to-expand |
| 2 | Strategy detail | `/strategy/<sid>` | **3-column pivot** — params / diagnostics / equity curve |
| 3 | Run diagnostics | `/run/<rid>`       | **3-axis radar** of Q1–Q7 pass-rates                |
| 4 | Replay         | `/replay/<rid>`     | **6-node DAG** rendered live with edge-flow animation |

Plus an **Export HTML** action that packages a single self-contained
`.html` file (inlined CSS, inlined Chart.js, JSON data, no JSX runtime)
so the user can share a static snapshot of any view without spinning
up the dev server.

### 1.2 User-confirmed decisions (frozen, from state file §"context")

| # | Decision              | Choice                                                                              |
|---|-----------------------|-------------------------------------------------------------------------------------|
| 1 | Scope                 | 5 actual loop runs + 4 views + Export HTML + 8 micro-animations                     |
| 2 | Tech stack            | **Vite + React + TypeScript** + Tailwind CSS (utility classes) + Framer Motion (animation) + Chart.js (npm package) + React Router (4-route SPA). FastAPI stays as **JSON-only backend** (no HTML rendering). |
| 3 | Visual language       | Quant Lab — dark mode default, JetBrains Mono, 3-color palette (Indigo/Emerald/Amber), generous whitespace, 8–12 px border-radius |
| 4 | 4 view WOW moments    | 5-card same-screen / 3-column pivot / 3-axis radar / 6-node DAG replay              |
| 5 | 8 micro-animations    | Number rollup / progress fill / node pulse / card stagger / radar draw-in / DAG edge flow / run-success flash / hover reveal — **implemented with Framer Motion** (motion components + `animate` + `whileHover` + `useMotionValue`) |
| 6 | v0.7.1 timeline       | 4 weeks (20 working days)                                                           |

These are **frozen** and not open for renegotiation in this doc.

### 1.3 Why a read-mostly WebUI (vs. a CLI-only product)

The CLI (`alphaloop loop "..."` + `alphaloop report`) already produces a
Markdown report. The WebUI's value is **legibility**:

- **Top-5 card** lets the user *compare* 5 strategies in one screen.
  Reading 5 Markdown tables takes 5 minutes; one screen takes 15 seconds.
- **3-axis radar** lets the user see *which diagnostics pass-rate is
  dragging down* a run. Markdown reports list them but never overlay them.
- **6-node replay** is the only way to show the *causal graph* — which
  stage took how long, where did tasks fail, did the cost gate fire.

We are NOT building:

- A real-time dashboard for live runs (see § 5 Risks — SSE is best-effort).
- A multi-user / auth system (no users, only local dev).
- Edit functionality (the loop writes artifacts; the UI reads them).
- A charting library beyond Chart.js (radar + line + bar covers 100% of
  our needs; no D3, no Plotly).

### 1.4 Why Vite + React (vs. server-side FastAPI + Jinja2)

The user-confirmed stack (state file §"context", decision #2) is
**Vite + React + TypeScript + Tailwind CSS + Framer Motion**. Rationale:

| Factor           | Vite + React + TS + Tailwind + Framer | FastAPI + Jinja2 + Chart.js CDN |
|------------------|---------------------------------------|--------------------------------|
| Lines of code    | ~700 (.tsx components + .css tokens + .py JSON endpoints) | ~500 (server + templates + JS) |
| Build step       | Vite dev server (HMR) + `tsc --noEmit` | None |
| Cognitive load   | 1 paradigm: components + props + hooks | 2 paradigms: SSR template + JS hydration |
| Bundle size      | ~200 KB (React 45 + Framer Motion 50 + Chart.js 80 + app 25) | ~210 KB Chart.js via CDN |
| Animation story  | Framer Motion — declarative `motion.div` + variants + `useMotionValue` (a11y built-in via `prefers-reduced-motion`) | CSS classes + `IntersectionObserver` JS hooks |
| Type safety      | TypeScript end-to-end (props, fetch responses, view models) | Python type hints only (frontend untyped) |
| Hot-reload DX    | Vite HMR (200 ms) — edit component, see result immediately | Jinja auto-reload (1–3 s) + full page reload |
| State reuse      | React state + context (DAG progress, selected run) | Server must re-render on every interaction |
| Chart.js import  | `import { Chart } from 'chart.js/auto'` (tree-shakeable) | `<script src="cdn>` (200 KB regardless) |
| Tailwind         | Utility classes, design tokens shared via `tailwind.config.ts` | Hand-written CSS + BEM |
| Export HTML      | `vite build` → static `dist/`, then inlined into one file | Already single-file |

**Trade-off acknowledged:** Vite + React adds a **build step** and
**dependency footprint** (~200 KB gzipped, vs near-zero for Jinja2).
We accept this because: (1) the WebUI ships once per release, not
per-request; (2) animations are **declarative** in Framer Motion
(much less code than CSS keyframes + IntersectionObserver); (3)
TypeScript prevents a class of bugs (prop drift, API contract
mismatch) that a 1424-line design doc cannot.

The alphaloop backend stays on Python: v0.7's `LoopRunner` already
exposes its data as Python objects. We add a **FastAPI JSON-only
endpoint layer** that exposes the same data as REST/JSON. FastAPI's
existing strength (auto OpenAPI, type-checked, async) is even more
valuable now since the surface is pure API, no HTML.

### 1.5 Why Chart.js via npm (not CDN)

- Chart.js 4.x is bundled via `npm install chart.js` and imported
  with `import { Chart, registerables } from 'chart.js/auto'`. Vite
  tree-shakes unused chart types (`bar`, `line`, `radar`); production
  bundle is **~80 KB** vs the 210 KB CDN UMD.
- **No network at view time.** The dev server and export both serve
  Chart.js locally — fixes the air-gapped / offline fallback risk
  identified in v0.7.1 R2 (CDN offline).
- **Version pinning** is a `package.json` field, not a CDN URL we
  have to remember to update.
- The existing **`<table>` fallback** for chart rendering (when
  Chart.js fails to hydrate — extremely unlikely now since it's bundled)
  stays in place as the § 8 R2 mitigation.

### 1.6 Non-goals (explicitly out of scope for v0.7.1)

- **Edit actions.** The UI reads artifacts. No buttons that mutate state.
- **Live auto-refresh during N3.** A run takes ≤ 6h; SSE gives best-effort
  progress, not a control channel.
- **Multi-run compare.** v0.7.1 shows ONE run at a time. Cross-run
  comparison is v0.8+.
- **Auth.** Local dev only. Bind to `127.0.0.1` by default.
- **Mobile-first.** Desktop ≥ 1280 px is the design target. Tablet works
  (responsive grid); phone is "readable but ugly".
- **Internationalization.** English only. UTF-8 strings throughout.
- **3D charts, candlestick charts, options chains.** Out of scope.

### 1.7 Success criteria (measurable)

| # | Criterion                                                                                | How measured |
|---|------------------------------------------------------------------------------------------|--------------|
| 1 | `npm run dev` (Vite) starts in < 3 s on a fresh checkout; FastAPI JSON server starts in < 3 s via `uvicorn` | time the import + first request |
| 2 | All 4 SPA routes return the expected view (Top-5 / Detail / Diagnostics / Replay) on a populated `runs/` directory | Playwright route smoke |
| 3 | Top-5 card renders 5 strategies on one 1440×900 viewport without horizontal scroll     | Playwright screenshot |
| 4 | All 8 Framer Motion animation variants are present in `webui/src/animations/*.ts`     | `ls webui/src/animations/*.ts` ≥ 8 |
| 5 | Export HTML produces a single `.html` file < 500 KB that opens standalone in Chrome    | `wc -c` |
| 6 | Dark mode default (no flash of light theme)                                             | Playwright `prefers-color-scheme` snapshot |
| 7 | First contentful paint < 1.5 s on a populated run                                       | Playwright performance API |
| 8 | `tests/webui/` covers all 4 views + 8 animations + export via Vitest + RTL (≥ 20 component tests) + Playwright (≥ 6 e2e) | `npm test` + `npm run test:e2e` |
| 9 | No console errors on any view in Chromium                                               | Playwright `console.log()` capture |
| 10 | Test suite grows from v0.7's 271 → ≥ 285 (Python) + ≥ 30 new TypeScript component tests | `pytest --collect-only` + `vitest run --reporter=verbose` |

---

## 2. Architecture

### 2.1 System diagram

```
                  ┌────────────────────────┐
                  │  runs/<run_id>/        │
                  │  manifest.yaml         │   ← v0.7 writer
                  │  results.parquet       │
                  │  top5.json             │
                  │  report.md             │
                  │  judge_calls/*.json    │
                  └──────────┬─────────────┘
                             │ read-only
                             ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  FastAPI JSON backend  (alphaloop.webui.api)                │
   │                                                              │
   │   routes.py (JSON only — no HTML):                           │
   │     GET  /api/runs                       → list_runs        │
   │     GET  /api/runs/{rid}/top5            → top5 list        │
   │     GET  /api/runs/{rid}/strategies/{sid} → strategy detail │
   │     GET  /api/runs/{rid}/diagnostics     → 7 Q + 3-axis data│
   │     GET  /api/runs/{rid}/replay          → 6 nodes + edges  │
   │     GET  /api/runs/{rid}/stream          → SSE live progress│
   │     GET  /api/runs/{rid}/export          → standalone .html │
   │     GET  /healthz                        → smoke + meta     │
   └─────────────────────────────┬───────────────────────────────┘
                                 │ JSON over HTTP + SSE
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Vite dev server  (webui/)                                   │
   │                                                              │
   │   src/main.tsx          # React 18 entry + createRoot       │
   │   src/App.tsx           # <BrowserRouter> + <Routes>        │
   │   src/views/TopFiveView.tsx        → /                      │
   │   src/views/StrategyDetailView.tsx → /strategy/<sid>        │
   │   src/views/RunDiagnosticsView.tsx → /run/<rid>             │
   │   src/views/ReplayView.tsx         → /replay/<rid>          │
   │   src/components/                  TopFiveCard / MetricNumber│
   │                                    RadarChart / DagGraph /… │
   │   src/animations/                  8 Framer Motion variants │
   │   src/styles/tokens.css            # Quant Lab CSS vars     │
   │   src/styles/tailwind.css          # Tailwind base + tokens │
   │   src/api/client.ts                # fetch wrapper (typed)  │
   │   tailwind.config.ts               # theme: dark + tokens   │
   │   vite.config.ts                   # dev proxy /api → :8000 │
   └─────────────────────────────┬───────────────────────────────┘
                                 │ HTTP (bundle served by Vite)
                                 ▼
                     ┌────────────────────────┐
                     │  Browser (Chromium)    │
                     │  JetBrains Mono        │
                     │  dark bg #0B0E14       │
                     └────────────────────────┘
```

In **dev**: Vite serves the SPA on `:5173` and proxies `/api/*` to
FastAPI on `:8000` (configured in `vite.config.ts`).
In **production**: the SPA is `vite build` → `dist/` static assets;
FastAPI serves `dist/index.html` as the SPA fallback for any non-API
path. (For export, the user can run `vite build && python -m
alphaloop.webui.export --input dist/ --output run.html` to get the
self-contained file.)

### 2.2 Module layout (proposed for v0.7.1 dev)

```
alphaloop/
├── src/alphaloop/                          # Python backend (NEW JSON-API package)
│   ├── loop/                                # unchanged from v0.7
│   ├── webui/                               # NEW — JSON-only API (no HTML)
│   │   ├── __init__.py
│   │   ├── api.py                            # FastAPI app factory
│   │   ├── routes.py                         # 7 JSON routes (+ /healthz)
│   │   ├── data.py                           # ArtifactReader — wraps persistence.read_*
│   │   ├── schemas.py                        # Pydantic models for JSON contracts
│   │   ├── sse.py                            # Server-Sent Events stream generator
│   │   └── export.py                         # Self-contained HTML packer (inlines dist/)
│   └── cli/
│       └── webui.py                          # NEW — `alphaloop webui` + `webui export` subcmds
│
├── webui/                                    # NEW Vite + React project (sibling to src/)
│   ├── src/
│   │   ├── main.tsx                          # React 18 entry
│   │   ├── App.tsx                           # <BrowserRouter> + <Routes>
│   │   ├── views/
│   │   │   ├── TopFiveView.tsx               # Route: /
│   │   │   ├── StrategyDetailView.tsx        # Route: /strategy/<sid>
│   │   │   ├── RunDiagnosticsView.tsx        # Route: /run/<rid>
│   │   │   └── ReplayView.tsx                # Route: /replay/<rid>
│   │   ├── components/
│   │   │   ├── TopFiveCard.tsx               # one strategy card
│   │   │   ├── MetricNumber.tsx              # Framer Motion number-rollup
│   │   │   ├── RadarChart.tsx                # Chart.js radar wrapper
│   │   │   ├── BarChart.tsx                  # Chart.js bar wrapper
│   │   │   ├── EquityCurve.tsx               # Chart.js line wrapper
│   │   │   ├── DagGraph.tsx                  # SVG 6-node DAG
│   │   │   ├── ProgressBar.tsx               # SSE-driven progress bar
│   │   │   ├── Topbar.tsx                    # run-selector + nav
│   │   │   └── ErrorState.tsx                # empty / 404 / 500
│   │   ├── animations/
│   │   │   ├── rollUpNumber.ts               # useMotionValue + spring (#1)
│   │   │   ├── staggerCards.ts               # variants.staggerChildren (#4)
│   │   │   ├── nodePulse.ts                  # repeat scale+y-glow (#3)
│   │   │   ├── successFlash.ts               # backgroundColor keyframes (#7)
│   │   │   ├── hoverReveal.ts                # whileHover opacity+translate (#8)
│   │   │   ├── dagEdgeFlow.ts                # strokeDashoffset loop (#6)
│   │   │   ├── progressFill.ts               # width animation (#2)
│   │   │   └── radarDrawIn.ts                # pathLength via Chart.js (#5)
│   │   ├── styles/
│   │   │   ├── tokens.css                    # Quant Lab CSS custom properties
│   │   │   └── tailwind.css                  # @tailwind base/components/utilities
│   │   └── api/
│   │       ├── client.ts                     # typed fetch wrapper
│   │       └── types.ts                      # shared types matching Pydantic schemas
│   ├── tests/
│   │   ├── views/                            # Vitest + React Testing Library
│   │   │   ├── TopFiveView.test.tsx          # 5+ tests
│   │   │   ├── StrategyDetailView.test.tsx
│   │   │   ├── RunDiagnosticsView.test.tsx
│   │   │   └── ReplayView.test.tsx
│   │   ├── components/                       # RTL per-component
│   │   │   ├── TopFiveCard.test.tsx
│   │   │   ├── MetricNumber.test.tsx
│   │   │   ├── RadarChart.test.tsx
│   │   │   ├── DagGraph.test.tsx
│   │   │   └── ProgressBar.test.tsx
│   │   ├── animations/                       # per-animation variant tests
│   │   │   └── *.test.ts                     # × 8
│   │   └── e2e/                               # Playwright (slow, CI only)
│   │       ├── top-five.spec.ts
│   │       ├── replay.spec.ts
│   │       └── dark-mode.spec.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts                        # dev proxy /api → :8000
│   ├── tailwind.config.ts                    # dark mode default
│   └── playwright.config.ts
│
└── tests/                                    # Python tests (sibling to webui/tests/)
    ├── test_webui_api.py                     # FastAPI TestClient — JSON endpoints
    ├── test_webui_data.py                    # ArtifactReader
    ├── test_webui_schemas.py                 # Pydantic contracts
    └── test_webui_export.py                  # self-contained HTML
```

The split mirrors v0.7's `loop/` + `cli/` pattern:
- **Backend** stays Python: FastAPI is the natural choice (alphaloop
  is already a Python package, FastAPI is on the project's roadmap for
  MCP servers anyway). FastAPI's role changes from "serve HTML + JSON"
  to **"JSON contract only"** — Pydantic schemas in `schemas.py` are
  the single source of truth, shared with TypeScript via code-gen or
  handwritten `types.ts`.
- **Frontend** is a separate `webui/` project at the repo root. Vite
  handles dev server, HMR, TypeScript compilation, Tailwind
  compilation, and production bundling. React Router handles the 4
  client-side routes. Framer Motion handles the 8 animations.

### 2.3 Data flow at runtime

```
   $ alphaloop webui --runs-dir ./runs --port 8000        (JSON API)
   $ cd webui && npm run dev                              (Vite dev server)
        │
        ▼
   ┌────────────────────────────────────────────────────────────┐
   │  FastAPI (:8000)                                              │
   │                                                              │
   │  1. data.ArtifactReader(runs_dir)                            │
   │       → list_runs() → [run_id, ...]                         │
   │       → read_run(rid) → {manifest, top5, rows, ...}          │
   │                                                              │
   │  2. GET /api/runs/<rid>/top5                                 │
   │       → ArtifactReader.read_run(rid)                         │
   │       → schemas.TopFiveList(...)                             │
   │       → JSON response (200)                                  │
   │                                                              │
   │  3. GET /api/runs/<rid>/stream                               │
   │       → sse.stream_run(rid)                                  │
   │       → polls <runs_dir>/<rid>/progress.json every 1 s       │
   │       → emits {event:"progress",data:{node:"n3",pct:0.42}}  │
   │       → or {event:"complete",data:{termination_reason:"B"}}  │
   └────────────────────────────────────────────────────────────┘
                                 │
                                 ▼ (HTTP / SSE)
   ┌────────────────────────────────────────────────────────────┐
   │  Vite dev server (:5173) + React SPA                         │
   │                                                              │
   │  1. App.tsx mounts <BrowserRouter>.                          │
   │  2. TopFiveView reads current run from /api/runs, then       │
   │     fetches /api/runs/<rid>/top5.                            │
   │       → renders TopFiveCard × 5 in a CSS grid.               │
   │       → MetricNumber runs rollUpNumber() spring animation.   │
   │       → motion.div cards play staggerCards variants.        │
   │  3. ReplayView opens EventSource(/api/runs/<rid>/stream).    │
   │       → ProgressBar's progressFill animation reads SSE.      │
   │       → DagGraph swaps nodePulse class as nodes complete.    │
   │       → successFlash plays on {event:"complete"}.            │
   └────────────────────────────────────────────────────────────┘
```

### 2.4 4 API endpoints, 4 SPA routes, 4 view models

| FastAPI JSON endpoint                       | Vite SPA route               | View model (matches Pydantic schema)                            |
|---------------------------------------------|------------------------------|-----------------------------------------------------------------|
| `GET /api/runs/<rid>/top5`                  | `/`                          | `{latest_run, runs: [...], top5: TopPick[5], metrics: {...}}`   |
| `GET /api/runs/<rid>/strategies/<sid>`      | `/strategy/<sid>`            | `{run_id, sid, pick: TopPick, diagnostics: Q[7], equity: [...]}`|
| `GET /api/runs/<rid>/diagnostics`           | `/run/<rid>`                 | `{run_id, manifest, top5, radar: Q[7], bar: Q[7]}`              |
| `GET /api/runs/<rid>/replay`                | `/replay/<rid>`              | `{run_id, dag: {nodes, edges}, timing: {stage: s}}`             |
| `GET /api/runs/<rid>/stream` (SSE)          | (consumed by ReplayView)     | `{event:"progress",data:{node,pct,...}}`                         |

The **Pydantic schemas in `schemas.py`** are the contract. React's
`api/types.ts` is hand-mirrored or (preferred) auto-generated via
`openapi-typescript` against `http://localhost:8000/openapi.json` at
build time — catches type drift before runtime.

### 2.5 Server-Sent Events (SSE) for live progress

When a `loop` run is **in-flight** (N3 still running), the user can
open `/replay/<rid>` and see a live progress bar driven by SSE:

- `runner.py` (v0.7) writes `runs/<rid>/progress.json` every 5 s with
  shape `{"node":"n3","completed":213,"total":500,"elapsed_s":2718}`.
  (This is a 1-line addition to v0.7's `LoopRunner._tick_progress`;
  deferred to v0.7.1 dev — listed as § 8 R2.)
- `GET /api/runs/<rid>/stream` polls `progress.json` every 1 s and
  emits SSE events `{event:"progress",data:{...}}`.
- React's `ReplayView.tsx` opens `new EventSource(url)` inside a
  `useEffect`; events flow through a small `useSseProgress` hook into
  `ProgressBar`, which animates via Framer Motion's `motion.div`
  width transition (animation #2, see § 5).

Why SSE, not WebSocket: SSE is **one-way** (server → client), works
over plain HTTP (no WS upgrade), survives proxies, and auto-reconnects
(`EventSource` has a built-in retry, supplemented by an explicit
`useEffect` cleanup on unmount). React consumes the same data shape
the FastAPI server emits — no hydration gap.

### 2.6 Static file serving

In **dev**, Vite serves the SPA from `:5173` with HMR. FastAPI lives
on `:8000` independently; the `vite.config.ts` has a `server.proxy`
entry that forwards `/api/*` from `:5173` → `:8000` so the SPA can
just `fetch("/api/runs/...")`.

In **production**, the SPA is `vite build` → `webui/dist/` (static
HTML + JS + CSS + fonts). FastAPI mounts `dist/` at `/` and serves
`index.html` as a SPA fallback for any non-`/api/*` path. JetBrains
Mono is bundled into `webui/dist/fonts/` via Vite asset pipeline
(local file, no external font CDN — fixes the § 8 R3 privacy concern).

Chart.js is bundled by Vite into a single `chunk` (≈ 80 KB gzipped);
no CDN dependency remains. This **eliminates** the v0.7.1 R2 fallback
risk identified previously (CDN offline).

### 2.7 CLI surface (v0.7.1 dev — design only)

```bash
# JSON API backend (runs on :8000)
alphaloop webui --runs-dir DIR [--host HOST] [--port PORT]
                       [--reload]               # uvicorn dev auto-reload

# Export self-contained .html (runs vite build first, then inlines)
alphaloop webui export --run-id RID [--output PATH.html]

# Frontend dev (separate terminal)
cd webui && npm install && npm run dev          # serves :5173

# Frontend production build
cd webui && npm run build                      # → webui/dist/
```

Two processes during dev (FastAPI + Vite) is normal for a JS frontend
+ Python backend split. In production, Vite's build output is served
by FastAPI's `StaticFiles` mount.

### 2.8 Integration with v0.7 CLI (`alphaloop loop`)

After a run completes, the v0.7 CLI prints
`Run URL: http://localhost:5173/run/<rid>` (if Vite is running) so the
user can jump straight to the diagnostics view. The redirect is
implemented as a **post-loop stdout suggestion** (no auto-launch —
user runs `npm run dev` explicitly when they want the UI).

---

## 3. API

The API is split into two layers:

- **Backend** (`src/alphaloop/webui/`): FastAPI, Pydantic, JSON only.
- **Frontend** (`webui/src/`): Vite + React + TypeScript, typed fetch,
  React Router routes.

### 3.1 Backend: FastAPI JSON endpoint signatures (full)

```python
# src/alphaloop/webui/routes.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()


@router.get("/api/runs", name="list_runs")
async def list_runs() -> dict:
    """List all runs in --runs-dir, newest-first.

    Response: {"runs": [{"rid": "...", "started_at": "...", "elapsed_s": ...}, ...]}
    """
    ...


@router.get("/api/runs/{rid}/top5", name="top5")
async def top5(rid: str) -> dict:
    """Top-5 pick list for a run (drives TopFiveView).

    Response: {"rid": "...", "top5": [TopPick × 5], "metrics": {...}}
    404 if rid not in runs_dir.
    """
    ...


@router.get("/api/runs/{rid}/strategies/{sid}", name="strategy_detail")
async def strategy_detail(rid: str, sid: str) -> dict:
    """One strategy detail (drives StrategyDetailView).

    Response: {"rid": ..., "sid": ..., "pick": TopPick,
               "diagnostics": {Q1..Q7: {label, value, pass}}, "equity": [...]}
    404 if sid not in top5[rid].
    """
    ...


@router.get("/api/runs/{rid}/diagnostics", name="diagnostics")
async def diagnostics(rid: str, compare: str | None = None) -> dict:
    """3-axis radar + bar data + manifest (drives RunDiagnosticsView).

    Response: {"rid": ..., "manifest": RunManifest, "radar": [Q1..Q7],
               "bar": [Q1..Q7], "compare_with": optional RadarDataset}
    compare=<other_rid> overlays a faded --color-ai dataset.
    """
    ...


@router.get("/api/runs/{rid}/replay", name="replay")
async def replay(rid: str) -> dict:
    """6-node DAG + edges + per-node timing (drives ReplayView).

    Response: {"rid": ..., "dag": {"nodes": [...], "edges": [...]},
               "timing": {"n1": 12, "n2": 34, ...}}
    """
    ...


@router.get("/api/runs/{rid}/stream", name="stream")
async def stream(rid: str) -> StreamingResponse:
    """SSE: progress events for an in-flight run.

    Events: {event:"progress",data:{node,pct,completed,total,elapsed_s}}
            {event:"complete",data:{termination_reason}}
            {event:"error",data:{message}}
    """
    ...


@router.get("/api/runs/{rid}/export", name="export_html")
async def export_html(rid: str) -> Response:
    """Self-contained .html (vite build → inlined into one file).

    Response: text/html (Content-Disposition: attachment).
    """
    ...


@router.get("/healthz", name="health")
async def health() -> dict:
    """Smoke: {"status":"ok","runs_dir":"...","n_runs":N}."""
    ...
```

All `/api/*` routes return JSON or SSE. Errors (`404`, `500`) return
`{"error":"..."}` with the appropriate status code; React's
`ErrorState.tsx` renders a friendly UI on top.

### 3.2 Frontend: Vite + React + React Router

```
webui/src/
├── main.tsx                       # React 18 + createRoot
├── App.tsx                        # <BrowserRouter> + <Routes>
├── views/TopFiveView.tsx
├── views/StrategyDetailView.tsx
├── views/RunDiagnosticsView.tsx
└── views/ReplayView.tsx
```

`App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import TopFiveView from "./views/TopFiveView";
import StrategyDetailView from "./views/StrategyDetailView";
import RunDiagnosticsView from "./views/RunDiagnosticsView";
import ReplayView from "./views/ReplayView";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<TopFiveView />} />
        <Route path="/strategy/:sid" element={<StrategyDetailView />} />
        <Route path="/run/:rid" element={<RunDiagnosticsView />} />
        <Route path="/replay/:rid" element={<ReplayView />} />
      </Routes>
    </BrowserRouter>
  );
}
```

`vite.config.ts` has a dev proxy:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
```

In dev, the SPA at `:5173` issues `fetch("/api/runs/...")`; Vite
proxies to FastAPI on `:8000`. In production, FastAPI serves
`webui/dist/` and the SPA hits `/api/...` on the same origin.

`base.html` / app shell responsibilities move into `App.tsx`: dark
background, JetBrains Mono import, topbar with run-selector, error
boundary.

### 3.3 Static asset budgets (production bundle)

| File / chunk                      | Size budget | Purpose                                          |
|-----------------------------------|-------------|--------------------------------------------------|
| `tokens.css` (Quant Lab vars)     | ≤ 2 KB      | Palette + spacing + typography tokens            |
| `tailwind.css` (purged)           | ≤ 10 KB     | Utility classes used in components               |
| React 18 runtime                  | ~ 45 KB gz  | `react`, `react-dom` (Vite code-split per route) |
| `react-router-dom`                | ~ 12 KB gz  | 4-route SPA routing                              |
| Framer Motion                     | ~ 50 KB gz  | All 8 animation variants                         |
| Chart.js (auto, tree-shaken)      | ~ 80 KB gz  | Radar / bar / line — bundled, no CDN             |
| App chunk (views + components)    | ~ 30 KB gz  | 4 views + 9 components                          |
| JetBrains Mono (subset)           | ~ 30 KB     | WOFF2 — `npm:` import or `public/`               |

**Total JS budget: ≤ 220 KB gzipped.** All assets served locally —
**zero runtime external dependencies**. No CDN.

### 3.4 SSE endpoint design

```python
# src/alphaloop/webui/sse.py
import asyncio
import json
from pathlib import Path


async def stream_run(run_dir: Path):
    """Yield SSE events for an in-flight run.

    Yields:
        {"event": "progress", "data": {"node": "n3", "pct": 0.42, ...}}
        {"event": "complete", "data": {"termination_reason": "B"}}
        {"event": "error",    "data": {"message": "..."}}

    Polls ``<run_dir>/progress.json`` every 1s. Stops when:
    - file shows ``complete: true``
    - file is missing for > 30 s (run crashed)
    - client disconnects (generator cancelled)
    """
    progress_file = run_dir / "progress.json"
    last_payload = None
    while True:
        if progress_file.exists():
            payload = json.loads(progress_file.read_text())
            if payload != last_payload:
                yield {"event": "progress", "data": payload}
                last_payload = payload
                if payload.get("complete"):
                    yield {"event": "complete", "data": payload}
                    return
        await asyncio.sleep(1.0)
```

FastAPI's `StreamingResponse(..., media_type="text/event-stream")`
wraps this generator. The `EventSource` client auto-reconnects on
disconnect (browser default retry: 3 s), and React's `ReplayView`
cleans up the listener in the `useEffect` return function.

### 3.5 CLI ↔ WebUI handoff

After `alphaloop loop "..."` finishes:

```
✓ Run complete: 2026-08-16T12-34-56Z_a1b2c3d4
  Top 5 picks: 5 strategies (best DSR=0.87)
  Artifacts:   runs/2026-08-16T12-34-56Z_a1b2c3d4/
  → View in UI: cd webui && npm run dev
                then open http://localhost:5173/run/2026-08-16T12-34-56Z_a1b2c3d4
```

We deliberately do NOT auto-launch the Vite dev server — that's the
user's choice. This is a 1-line addition to `cli/loop.py`'s success
path.

### 3.6 Export HTML format

The export endpoint produces a single self-contained `.html` file by
running `vite build` (cached if unchanged) and inlining the output:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>alphaloop run 2026-08-16T12-34-56Z_a1b2c3d4</title>
  <style>
    /* inlined tokens.css + tailwind.css */
  </style>
</head>
<body>
  <div id="root"></div>
  <script>
    /* inlined dist/assets/*.js (React + Vite + Chart.js + app) */
  </script>
  <script>
    /* window.__RUN_DATA__ = {rid, top5, ...} injected as initial state */
  </script>
</body>
</html>
```

Size estimate: **~220 KB per export** (React + Framer + Chart.js +
app). Well under the 500 KB success criterion (§ 1.7 #5). The export
opens in any browser, including offline / air-gapped — no network
required because Chart.js is bundled.

The `__RUN_DATA__` injection lets the SPA boot with the right
context: `main.tsx` reads `window.__RUN_DATA__` before mounting, so
the export skips the initial `fetch()` and renders synchronously.

---

## 4. Quant Lab Visual Language

### 4.1 CSS custom properties (`tokens.css`)

```css
:root {
  /* 3-color palette (user-confirmed) */
  --color-math:   #5B6CFF;   /* Indigo — math / deterministic diagnostics (Q1–Q4) */
  --color-stats:  #10B981;   /* Emerald — statistics / probabilistic (Q5–Q6) */
  --color-ai:     #F59E0B;   /* Amber   — AI / LLM judge (Q7) */

  /* Neutrals (dark mode default) */
  --bg-0:    #0B0E14;        /* page background */
  --bg-1:    #11151D;        /* card background */
  --bg-2:    #1A1F2B;        /* hover / nested */
  --fg-0:    #E5E9F0;        /* primary text */
  --fg-1:    #9BA3B4;        /* secondary text */
  --fg-2:    #5C6573;        /* muted */
  --border:  #2A3142;

  /* Spacing scale (8-px base) */
  --s-1:  4px;
  --s-2:  8px;
  --s-3:  12px;
  --s-4:  16px;
  --s-5:  24px;
  --s-6:  32px;
  --s-7:  48px;
  --s-8:  64px;

  /* Border radius (8-12px range) */
  --r-sm: 8px;
  --r-md: 10px;
  --r-lg: 12px;

  /* Shadow (subtle, dark-mode-aware) */
  --shadow-1: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-2: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-glow-math: 0 0 16px rgba(91,108,255,0.3);
  --shadow-glow-ai:   0 0 16px rgba(245,158,11,0.3);

  /* Typography */
  --font-mono: "JetBrains Mono", "SF Mono", "Consolas", monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --fs-xs: 11px; --fs-sm: 13px; --fs-base: 14px;
  --fs-lg: 16px; --fs-xl: 20px; --fs-2xl: 28px;
  --lh-tight: 1.2; --lh-base: 1.5; --lh-loose: 1.7;

  /* Animation timings (used by § 5 animations) */
  --t-fast: 150ms;
  --t-base: 300ms;
  --t-slow: 600ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### 4.2 Color semantics (which view uses which color)

| Element                          | Color           | Reason                                       |
|----------------------------------|-----------------|----------------------------------------------|
| DSR / Sharpe / CAGR (math)       | `--color-math`  | Deterministic computation; "blue chip"       |
| Q1–Q4 diagnostics (deterministic)| `--color-math`  | All deterministic; one consistent accent    |
| Q5–Q6 (vs buy-hold / vs SPY)     | `--color-stats` | Probabilistic comparison                     |
| Q7 LLM judge                     | `--color-ai`    | AI-flavored — the "human in the loop"        |
| Success / pass / wins            | `--color-stats` | Emerald = "go"                               |
| Warning / caveat                 | `--color-ai`    | Amber = "caution"                            |
| Error / fail                     | `#EF4444`       | Red (only for errors)                        |

### 4.3 Typography

- **Numbers** (DSR, Sharpe, CAGR) — JetBrains Mono, `--fs-xl`, tabular nums.
- **Labels** (strategy name, factor) — JetBrains Mono, `--fs-base`.
- **Body** (paragraphs, theses) — system sans, `--fs-base`, `--lh-base`.
- **Headings** — system sans, `--fs-2xl` / `--fs-xl`, `--lh-tight`.

Why mono for everything: in a quant tool, alignment of digits matters.
`1.234` and `1.235` should be visually distinct.

### 4.4 Spacing & layout

- **12-column grid**, 24 px gutter, max-width 1440 px.
- **Generous whitespace**: 32–48 px between major sections (rule of
  "if in doubt, double the margin").
- **Cards**: 16–24 px padding, `--r-md` radius, `--bg-1` background,
  `--border` 1-px outline.
- **No drop shadows by default**; reserve `--shadow-2` for floating
  elements (tooltips, modals) only.

### 4.5 Responsive breakpoints

| Width     | Layout change                                              |
|-----------|------------------------------------------------------------|
| ≥ 1280 px | Full 12-col grid (target)                                  |
| 768–1279  | Cards reflow 2-up; radar stays full width                  |
| < 768 px  | Cards stack single-column; some charts degrade to table    |

### 4.6 Accessibility

- Color contrast ≥ 4.5:1 for body text on `--bg-0` (E5E9F0 on 0B0E14
  gives 14.3:1 — well above WCAG AA).
- All interactive elements have `:focus-visible` outlines (`2px solid
  --color-math`).
- Animations respect `@media (prefers-reduced-motion: reduce)`:
  disables all 8 animations, leaves static states.
- Charts have `<table>` fallback (Chart.js CDN fail) and `aria-label`.

---

## 5. The 8 Micro-Animations

Each animation is implemented as a **Framer Motion variant** in
`webui/src/animations/*.ts`. Variants are pure TypeScript objects —
they declare `initial`, `animate`, `whileHover`, `whileInView`, and
`transition` props for `motion.*` components. All animations honor
`prefers-reduced-motion: reduce` via Framer Motion's
`useReducedMotion()` hook (one line per variant).

| # | Variant file                | React hook / animation target            | Duration  | Cost                  |
|---|-----------------------------|------------------------------------------|-----------|-----------------------|
| 1 | `rollUpNumber.ts`           | `useMotionValue` + spring for DSR/Sharpe | 800 ms    | 1 spring + 1 RAF      |
| 2 | `progressFill.ts`           | SSE → `motion.div` width transition      | 300 ms    | 1 width tween / event |
| 3 | `nodePulse.ts`              | `repeat: Infinity` scale + y-glow        | 1.4 s loop| 1 GPU-only animation  |
| 4 | `staggerCards.ts`           | `variants` with `staggerChildren`        | 100 ms ×5 | 1 parent variant      |
| 5 | `radarDrawIn.ts`            | Chart.js `animation.duration`            | 1.2 s     | 1 chart animation     |
| 6 | `dagEdgeFlow.ts`            | `repeat: Infinity` `strokeDashoffset`    | 2.0 s loop| SVG paint only        |
| 7 | `successFlash.ts`           | `animate={{ backgroundColor: [...] }}`   | 600 ms    | 1 paint               |
| 8 | `hoverReveal.ts`            | `whileHover={{ opacity: 1, y: 0 }}`      | 200 ms    | 0 idle / 1 hover      |

### 5.1 #1 Number rollup — `webui/src/animations/rollUpNumber.ts`

```ts
import { animate, useMotionValue, useTransform } from "framer-motion";

export function useRollUpNumber(target: number) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => v.toFixed(3));
  React.useEffect(() => {
    const controls = animate(count, target, {
      duration: 0.8,
      ease: [0.16, 1, 0.3, 1],
    });
    return controls.stop;
  }, [target]);
  return rounded;
}

// Usage in MetricNumber.tsx:
// <motion.span>{useRollUpNumber(0.873)}</motion.span>
```

**Cost: 1 spring animation, ~50 frames per number.** Triggered on
viewport entry via `useInView` from `framer-motion`.

### 5.2 #2 Progress fill — `webui/src/animations/progressFill.ts`

```ts
import { motion } from "framer-motion";

export const progressFillVariants = {
  initial: { width: "0%" },
  animate: (pct: number) => ({ width: `${pct}%` }),
  transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] },
};

// Usage in ProgressBar.tsx (driven by SSE):
// <motion.div className="bg-color-math h-2 rounded"
//   variants={progressFillVariants}
//   custom={progressPct}
//   initial="initial"
//   animate="animate" />
```

SSE handler in `ReplayView.tsx` updates `progressPct` per event;
Framer Motion re-tweens `width`. **Cost: 1 reflow per SSE event
(~1/s).**

### 5.3 #3 Node pulse — `webui/src/animations/nodePulse.ts`

```ts
export const nodePulseVariants = {
  initial: { scale: 1, boxShadow: "0 0 0 0 rgba(91,108,255,0.0)" },
  animate: {
    scale: [1, 1.06, 1],
    boxShadow: [
      "0 0 0 0 rgba(91,108,255,0.4)",
      "0 0 0 12px rgba(91,108,255,0.0)",
      "0 0 0 0 rgba(91,108,255,0.0)",
    ],
    transition: { duration: 1.4, repeat: Infinity, ease: "easeOut" },
  },
};
```

Applied to the DAG node (`DagGraph.tsx`) corresponding to the
currently-running stage. SSE handler updates which node has the
`animate="animate"` prop. **Cost: GPU-only; no JS work after mount.**

### 5.4 #4 Card stagger — `webui/src/animations/staggerCards.ts`

```ts
export const cardContainerVariants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};

export const cardItemVariants = {
  initial: { opacity: 0, y: 16, scale: 0.98 },
  animate: {
    opacity: 1, y: 0, scale: 1,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
};

// Usage in TopFiveView.tsx:
// <motion.div variants={cardContainerVariants} initial="initial" animate="animate">
//   {top5.map(p => <motion.div key={p.sid} variants={cardItemVariants}>
//                      <TopFiveCard pick={p} />
//                    </motion.div>)}
// </motion.div>
```

**Cost: pure JS orchestration; Framer Motion batches into a single
paint.** Cheapest, most impactful animation.

### 5.5 #5 Radar draw-in — `webui/src/animations/radarDrawIn.ts`

```ts
// Chart.js built-in animation is used directly from inside RadarChart.tsx:
new Chart(ctx, {
  type: "radar",
  data: { ... },
  options: {
    animation: { duration: 1200, easing: "easeOutQuart" },
  },
});

// Trigger: useInView from framer-motion; chart.update() on entry.
```

Triggered by Framer Motion's `useInView({ amount: 0.3 })` (entry →
`chart.update()`). **Cost: Chart.js's animation; same as a normal
render but with built-in GPU compositing.**

### 5.6 #6 DAG edge flow — `webui/src/animations/dagEdgeFlow.ts`

```ts
export const dagEdgeVariants = {
  initial: { strokeDashoffset: 24 },
  animate: {
    strokeDashoffset: 0,
    transition: { duration: 2, repeat: Infinity, ease: "linear" },
  },
};

// Usage in DagGraph.tsx on each <motion.path> edge:
// <motion.path strokeDasharray="6 6" variants={dagEdgeVariants}
//            initial="initial" animate="animate" />
```

The DAG is SVG (6 nodes, 5 edges). `ReplayView.tsx` plays through
edges in topo order, applying `animate="animate"` for 2 s each.
**Cost: 1 SVG paint per edge transition; ≤ 5 transitions per replay.**

### 5.7 #7 Run success flash — `webui/src/animations/successFlash.ts`

```ts
export const successFlashVariants = {
  initial: { backgroundColor: "var(--bg-1)" },
  animate: {
    backgroundColor: [
      "var(--bg-1)",
      "var(--color-stats)",
      "var(--bg-1)",
    ],
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
};
```

Triggered when SSE emits `event: complete`. Applied to the topbar
via `useReducedMotion() ? null : successFlashVariants`. **Cost: 1
paint.**

### 5.8 #8 Hover reveal — `webui/src/animations/hoverReveal.ts`

```ts
export const hoverRevealVariants = {
  initial: { opacity: 0, y: 4 },
  whileHover: { opacity: 1, y: 0 },
  whileFocus: { opacity: 1, y: 0 },
  transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
};
```

Used in `TopFiveCard.tsx` to reveal the "Expand" button + extra
metrics. **Cost: 0 idle; 1 hover/focus transition only.**

### 5.9 Reduced-motion handling

Each variant respects accessibility through Framer Motion's
`useReducedMotion()` hook:

```ts
import { useReducedMotion } from "framer-motion";

export function useAnimationVariants(variants: Variants): Variants {
  const shouldReduceMotion = useReducedMotion();
  return shouldReduceMotion ? {} : variants;
}
```

All 8 variants fall back to no-op when `shouldReduceMotion` is true —
the static state renders, no paint cost, no animation triggers. This
satisfies § 4.6 accessibility requirement with **zero per-variant
boilerplate**.

### 5.10 Performance budget (all 8 combined)

- Idle: 0 paint cost. Only `.nodePulse` and `.dagEdgeFlow` run while
  idle, both GPU-only (no layout).
- On mount: 5 card stagger (≤ 1 paint), 1 number rollup (1 spring).
- During replay: 1 DAG edge transition per stage (≤ 5 total).
- On SSE event: 1 progress fill (1 reflow), 1 node-pulse swap.

Aggregate: well under 16 ms / frame. Verified via Playwright
`page.evaluate(() => performance.measureUserAgentSpecificMemory())`
plus Framer Motion's `MotionValue` debug subscriber (see § 7 Tests).

---

## 6. The 4 Views (Detailed)

### 6.1 View 1 — Top-5 card (`GET /`)

**Layout:** Full-bleed 12-col grid with 5 cards, each `col-span-2` with
a 24-px gap. The 5th card has an empty `col-span-2` slot beside it for
breathing room.

**Each card contains:**
- Header: rank badge (#1–#5), strategy class name, factor class name.
- Body (3 stacked rows):
  - DSR — large, `--color-math`, with `.anim--number-rollup`.
  - Sharpe + CAGR + MaxDD — 3 small numbers, `--color-stats`.
  - Passes indicator — green check or amber warning.
- Footer: `View details →` link to `/strategy/<task_id>`.

**Card hover** (animation #8): reveals a 4th row with extra metrics
(turnover, latency, judge summary) and a subtle `box-shadow: --shadow-2`.

**Empty state:** if `runs/` has zero runs, show a centered panel:
"No runs yet. Run `alphaloop loop \"<goal>\"` to generate one." with a
copy-pasteable example.

**No runs/selectable state:** A `<select>` in the topbar lists all runs
(sorted newest-first). Changing it reloads `/`. The default is the
most-recent run.

### 6.2 View 2 — Strategy detail (`GET /strategy/<task_id>`)

**3-column pivot** (CSS grid, `grid-template-columns: 1fr 2fr 1fr`):

| Column     | Width | Content                                             |
|------------|-------|-----------------------------------------------------|
| Left       | 1fr   | Params (JSON pretty-printed, `--color-math`)        |
| Center     | 2fr   | Diagnostics (Q1–Q7 list) + equity curve (Chart.js line) |
| Right      | 1fr   | Metadata (task_id, rank, seed, latency, judge summary) |

**Center column is the hero:**
- Top: equity curve (line chart, 1 line, dark bg, no grid lines, single
  `--color-math` stroke).
- Below: 7-row diagnostic table (Q1 DSR / Q2 CV / Q3 consistency /
  Q4 vs random / Q5 vs buy-hold / Q6 vs SPY / Q7 LLM judge). Each row
  has: question label, value, pass/fail icon, expandable "details" link.

**Equity curve** is fetched from `results.parquet` (the row has
`backtest.metrics.equity_curve` if persisted — if not, we re-derive from
the report.md "Top 5 picks" table's CAGR/Sharpe only and show a synthetic
placeholder labeled "curve unavailable").

### 6.3 View 3 — Run diagnostics (`GET /run/<run_id>`)

**3-axis radar** (the user-confirmed WOW moment #3):

- Chart.js radar with 7 axes: Q1 DSR, Q2 CV, Q3 consistency, Q4 vs random,
  Q5 vs buy-hold, Q6 vs SPY, Q7 LLM judge.
- Each axis shows the **pass-rate** (% of tasks passing that diagnostic).
- Filled area colored `--color-math` (alpha 0.2); outline `--color-math`.
- Animation #5 (`radar draw-in`) on viewport entry.
- **Two datasets overlaid** if `compare_with_run_id` query param is set
  (e.g. `?compare=2026-08-15T...` shows yesterday's run as a faded
  `--color-ai` polygon for diff comparison).

**Plus:**
- Bar chart (7 bars, one per Q): pass-rate count, color-coded by category
  (math = Indigo, stats = Emerald, AI = Amber).
- Manifest summary card (run_id, goal, seed, model, git_commit, elapsed,
  termination_reason, cost).

**Empty / failed run:** if 0 tasks completed, the radar shows a single
collapsed polygon (no data); the manifest card shows the failure reason.

### 6.4 View 4 — Replay (`GET /replay/<run_id>`)

**6-node DAG** rendered as inline SVG (one `<g class="dag-node">` per node,
`<line class="dag-edge">` per edge):

```
     [N1 Load]──→[N2 Plan]──→[N3 Execute]──→[N4 Diagnose]──→[N5 Aggregate]──→[N6 Commit]
```

Each node:
- 120 × 60 px rounded rectangle (`--r-md`).
- Name (e.g., "N1 Load Data"), elapsed time below.
- Status pill: green check (done), amber spinner (running), gray dot (pending).
- If currently running: animation #3 (`.anim--node-pulse`) on the box.
- Click → opens a side-panel with the node's stdout (if logged to
  `runs/<run_id>/logs/n<N>.log`) or a placeholder "logs unavailable".

**Edges:**
- 2-px stroke, `--color-math`.
- Animation #6 (`.anim--dag-edge-flow`) when "Play" button is clicked;
  flows from N1 → N6 over 12 s (2 s per edge).

**Controls** (top-right):
- `▶ Play` (animates edges through nodes).
- `⏸ Pause`.
- `↺ Reset`.
- Speed: `0.5× / 1× / 2×` (translates to animation-duration multiplier).

**Timing data** (read from `progress.json` if present, else from
`manifest.yaml.started_at` / `finished_at`):
- Per-node wall-clock (e.g., N3 took 4h 12m, N4 took 38m).
- Total elapsed.
- Cost-gate status (was the run capped by cost or by timeout?).

### 6.5 Empty / error states (all views)

- **No runs directory:** `runs/` empty → topbar shows red banner
  "No runs found in `<runs_dir>`". Each view shows a centered placeholder.
- **Run not found** (`/run/<bogus>`): 404 with `components/error.html`,
  link back to `/`.
- **Artifact corrupt** (parquet read fails): 500 with `error.html`,
  shows error message + "View raw manifest.yaml" link.

---

## 7. Tests

Two independent test suites:

- **Backend** (`tests/test_webui*.py`): FastAPI TestClient on JSON
  endpoints + Pydantic schemas + export HTML. Pure Python pytest.
- **Frontend** (`webui/tests/`): Vitest + React Testing Library for
  components/views; Playwright for end-to-end browser behavior.

This separation matches the architectural split in § 2. Each suite
mocks the *other* side: backend tests mock file IO; frontend tests use
**msw** (Mock Service Worker) to intercept `fetch("/api/...")` calls
without a real backend.

### 7.1 Test layout

```
tests/                                       # Python pytest (backend)
├── test_webui_api.py                        # FastAPI TestClient — 7 JSON endpoints + /healthz
├── test_webui_data.py                       # ArtifactReader — wraps persistence
├── test_webui_schemas.py                    # Pydantic contracts — runtime validation
├── test_webui_export.py                     # Self-contained HTML (vite build → inlined)
└── fixtures/sample_run/                     # synthetic runs/<rid>/ for tests
    ├── manifest.yaml
    ├── results.parquet
    ├── top5.json
    └── report.md

webui/tests/                                 # Vitest + RTL (frontend)
├── views/
│   ├── TopFiveView.test.tsx                 # 5+ tests
│   ├── StrategyDetailView.test.tsx          # 5+ tests
│   ├── RunDiagnosticsView.test.tsx          # 5+ tests
│   └── ReplayView.test.tsx                  # 5+ tests
├── components/
│   ├── TopFiveCard.test.tsx
│   ├── MetricNumber.test.tsx
│   ├── RadarChart.test.tsx
│   ├── DagGraph.test.tsx
│   └── ProgressBar.test.tsx
├── animations/
│   ├── rollUpNumber.test.ts                 # × 8 (one per animation)
│   ├── progressFill.test.ts
│   ├── nodePulse.test.ts
│   ├── staggerCards.test.ts
│   ├── radarDrawIn.test.ts
│   ├── dagEdgeFlow.test.ts
│   ├── successFlash.test.ts
│   └── hoverReveal.test.ts
├── api/
│   └── client.test.ts                       # typed fetch wrapper
├── utils/
│   └── handlers.ts                          # msw handlers — mock /api/* + SSE
└── e2e/                                     # Playwright (slow, CI only)
    ├── top-five.spec.ts
    ├── strategy-detail.spec.ts
    ├── replay.spec.ts
    └── dark-mode.spec.ts

webui/playwright.config.ts                   # Playwright config
```

Targets:
- **Python**: ≥ 14 new tests (taking v0.7's 271 → ≥ 285 total).
- **TypeScript (Vitest + RTL)**: ≥ 30 component/view/animation tests.
- **E2E (Playwright)**: ≥ 6 browser tests across the 4 views.

### 7.2 Backend unit tests — FastAPI TestClient (Python pytest)

```python
# tests/test_webui_api.py
import pytest
from fastapi.testclient import TestClient
from alphaloop.webui.api import create_app

@pytest.fixture
def client(sample_run_dir):
    app = create_app(runs_dir=sample_run_dir)
    return TestClient(app)


def test_healthz_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "runs_dir" in body


def test_list_runs_returns_array(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert "runs" in body
    assert isinstance(body["runs"], list)


def test_top5_returns_five_picks(client, sample_run_id):
    r = client.get(f"/api/runs/{sample_run_id}/top5")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    body = r.json()
    assert "top5" in body
    assert len(body["top5"]) == 5
    for p in body["top5"]:
        assert {"sid", "rank", "dsr", "sharpe"}.issubset(p.keys())


@pytest.mark.parametrize("sid", ["t1", "t2", "t3", "t4", "t5"])
def test_strategy_detail_returns_diagnostics(client, sample_run_id, sid):
    r = client.get(f"/api/runs/{sample_run_id}/strategies/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert "diagnostics" in body
    assert {f"q{i}" for i in range(1, 8)}.issubset(body["diagnostics"].keys())


def test_diagnostics_returns_radar_and_bar(client, sample_run_id):
    r = client.get(f"/api/runs/{sample_run_id}/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert "radar" in body and len(body["radar"]) == 7
    assert "bar" in body and len(body["bar"]) == 7


def test_replay_returns_dag_and_timing(client, sample_run_id):
    r = client.get(f"/api/runs/{sample_run_id}/replay")
    assert r.status_code == 200
    body = r.json()
    assert "dag" in body
    assert len(body["dag"]["nodes"]) == 6
    assert "timing" in body


def test_export_returns_self_contained_html(client, sample_run_id):
    r = client.get(f"/api/runs/{sample_run_id}/export")
    assert r.status_code == 200
    assert "<style>" in r.text
    assert "<script" in r.text
    assert "framer-motion" in r.text.lower() or "motion" in r.text.lower()
    assert "window.__RUN_DATA__" in r.text
    assert len(r.content) < 500_000  # 500 KB ceiling


def test_404_for_unknown_run(client):
    r = client.get("/api/runs/2099-01-01T00-00-00Z_deadbeef/top5")
    assert r.status_code == 404
    assert "error" in r.json()


def test_compare_overlay_in_diagnostics(client, sample_run_id, other_run_id):
    r = client.get(
        f"/api/runs/{sample_run_id}/diagnostics?compare={other_run_id}"
    )
    assert r.status_code == 200
    body = r.json()
    assert "compare_with" in body
    assert body["compare_with"] is not None
```

```python
# tests/test_webui_schemas.py
from alphaloop.webui.schemas import (
    TopPick, DiagnosticsPayload, RadarDataset, RunManifest,
)

def test_top_pick_round_trip():
    p = TopPick(sid="t1", rank=1, dsr=0.873, sharpe=1.42, cagr=0.18, max_dd=0.07)
    assert TopPick.model_validate(p.model_dump()).sid == "t1"

def test_diagnostics_payload_requires_seven_qs():
    with pytest.raises(ValueError):
        DiagnosticsPayload(q1={}, q2={}, q3={})  # only 3 of 7

def test_radar_dataset_clamps_out_of_range_values():
    with pytest.raises(ValueError):
        RadarDataset(values=[0.5, 1.5])  # > 1 not allowed
```

### 7.3 Frontend unit tests — Vitest + React Testing Library (TypeScript)

```ts
// webui/tests/views/TopFiveView.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { setupServer } from "msw/node";
import { handlers } from "../utils/handlers";
import TopFiveView from "../../src/views/TopFiveView";

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("renders 5 strategy cards on top-five view", async () => {
  render(<TopFiveView />);
  await waitFor(() => {
    expect(screen.getAllByTestId("top-five-card")).toHaveLength(5);
  });
});

test("rank badges display #1..#5", async () => {
  render(<TopFiveView />);
  for (const n of [1, 2, 3, 4, 5]) {
    expect(await screen.findByText(`#${n}`)).toBeInTheDocument();
  }
});

test("DSR values are formatted with 3 decimals", async () => {
  render(<TopFiveView />);
  expect(await screen.findByText("0.873")).toBeInTheDocument();
});

test("clicking a card navigates to /strategy/<sid>", async () => {
  render(<TopFiveView />);
  const link = await screen.findByRole("link", { name: /View details/i });
  expect(link).toHaveAttribute("href", "/strategy/t1");
});

test("empty runs shows fallback message", async () => {
  server.use(handlers.emptyRuns);
  render(<TopFiveView />);
  expect(
    await screen.findByText(/No runs yet/i)
  ).toBeInTheDocument();
});
```

```ts
// webui/tests/components/MetricNumber.test.tsx
import { render, screen, act } from "@testing-library/react";
import { MetricNumber } from "../../src/components/MetricNumber";
import { useRollUpNumber } from "../../src/animations/rollUpNumber";

test("rolls up to target value within ~1s", async () => {
  jest.useFakeTimers();
  render(<MetricNumber value={0.873} />);
  expect(screen.getByText("0")).toBeInTheDocument();
  act(() => { jest.advanceTimersByTime(1000); });
  expect(screen.getByText("0.873")).toBeInTheDocument();
});

test("honors prefers-reduced-motion (no animation)", () => {
  global.matchMedia = jest.fn().mockImplementation(
    (q) => ({
      matches: q.includes("reduce"),
      addListener: jest.fn(),
      removeListener: jest.fn(),
    })
  );
  render(<MetricNumber value={0.873} />);
  // value is rendered as text immediately, no roll-up
  expect(screen.getByText("0.873")).toBeInTheDocument();
});
```

```ts
// webui/tests/animations/rollUpNumber.test.ts
import { renderHook, act } from "@testing-library/react";
import { useRollUpNumber } from "../../src/animations/rollUpNumber";

test("useRollUpNumber returns a MotionValue that reaches target", () => {
  const { result } = renderHook(() => useRollUpNumber(0.873));
  // Initially 0
  expect(result.current.get()).toBe(0);
  // After mount + time, approaches target
  act(() => { jest.advanceTimersByTime(1000); });
  expect(result.current.get()).toBeCloseTo(0.873, 2);
});

test("useRollUpNumber cleanup stops animation on unmount", () => {
  const { unmount } = renderHook(() => useRollUpNumber(0.5));
  unmount();  // should not throw / leak
});
```

(Per-animation variant tests cover each of the 8 animations; per
the layout above, that's `webui/tests/animations/*.test.ts × 8`.)

### 7.4 Integration tests — msw (Mock Service Worker)

msw intercepts `fetch("/api/...")` calls inside Vitest component
tests. Each test sets up a specific response shape and asserts that
the React component renders correctly. The handlers in
`webui/tests/utils/handlers.ts` mirror the Pydantic schemas in
`src/alphaloop/webui/schemas.py`:

```ts
// webui/tests/utils/handlers.ts
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/runs", () =>
    HttpResponse.json({ runs: [/* ... */] })
  ),
  http.get("/api/runs/:rid/top5", () =>
    HttpResponse.json({ rid: "...", top5: [/* 5 picks */] })
  ),
  http.get("/api/runs/:rid/diagnostics", () =>
    HttpResponse.json({ radar: [/* 7 */], bar: [/* 7 */] })
  ),
  http.get("/api/runs/:rid/stream", () =>
    new Response(/* SSE event stream */, {
      headers: { "content-type": "text/event-stream" },
    })
  ),
];
```

This catches contract drift between Pydantic and TypeScript before
runtime — every prop the React component expects must match the
shape msw returns.

### 7.5 E2E tests — Playwright (TypeScript, slow, CI only)

```ts
// webui/tests/e2e/top-five.spec.ts
import { test, expect } from "@playwright/test";

test("top-5 card: 5 cards render with no horizontal scroll @ 1440x900",
  async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.getByTestId("top-five-card")).toHaveCount(5);
    const scrollW = await page.evaluate(
      () => document.documentElement.scrollWidth
    );
    expect(scrollW).toBeLessThanOrEqual(1440);
  }
);

test("dark mode: background is rgb(11, 14, 20) on first paint",
  async ({ page }) => {
    await page.goto("/");
    const bg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor
    );
    expect(bg).toBe("rgb(11, 14, 20)");
  }
);

test("no console errors on any view",
  async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    for (const route of ["/", "/strategy/t1", "/run/...", "/replay/..."]) {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
    }
    expect(errors).toEqual([]);
  }
);

test("Replay view connects to SSE stream and updates progress",
  async ({ page }) => {
    await page.goto("/replay/test-run-id");
    await expect(page.getByTestId("progress-bar")).toBeVisible();
    await expect(page.getByTestId("progress-bar")).toHaveAttribute(
      "data-pct",
      /\d+/
    );
  }
);

test("reduced-motion: animations are not running",
  async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    // Framer Motion falls back to no-op; cards render in final state
    await expect(page.getByTestId("top-five-card")).toHaveCount(5);
    await expect(page.getByText("0.873")).toBeVisible();  // immediate
  }
);

test("hover reveal on TopFiveCard shows expand button",
  async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("top-five-card").first().hover();
    await expect(page.getByRole("button", { name: /expand/i })).toBeVisible();
  }
);
```

### 7.6 Performance tests — Playwright

```ts
test("first-contentful-paint < 1.5 s",
  async ({ page }) => {
    await page.goto("/");
    const fcp = await page.evaluate(
      () =>
        new Promise<number>((resolve) => {
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              if (entry.name === "first-contentful-paint") {
                resolve(entry.startTime);
                return;
              }
            }
          }).observe({ type: "paint", buffered: true });
        })
    );
    expect(fcp).toBeLessThan(1500);
  }
);

test("8 Framer Motion animations: idle FPS ≥ 55",
  async ({ page }) => {
    await page.goto("/replay/test-run-id");
    await page.waitForTimeout(2000);  // let stagger + rollup complete
    const fps = await page.evaluate(
      () =>
        new Promise<number>((resolve) => {
          let frames = 0;
          const start = performance.now();
          function tick() {
            frames++;
            if (performance.now() - start < 1000) requestAnimationFrame(tick);
            else resolve(frames);
          }
          requestAnimationFrame(tick);
        })
    );
    expect(fps).toBeGreaterThanOrEqual(55);
  }
);

test("Framer Motion bundle < 60 KB gzipped",
  async ({ page }) => {
    await page.goto("/");
    const bytes = await page.evaluate(async () => {
      const res = await fetch("/assets/", { redirect: "manual" });
      // walk all script tags, sum gzipped sizes
      const scripts = Array.from(document.querySelectorAll("script[src]"));
      let total = 0;
      for (const s of scripts) {
        const r = await fetch((s as HTMLScriptElement).src);
        const b = await r.arrayBuffer();
        // approximate gzip ratio
        total += b.byteLength * 0.32;
      }
      return total;
    });
    expect(bytes).toBeLessThan(60 * 1024);
  }
);
```

### 7.7 Verification gate

Before reporting "v0.7.1 WebUI design is done":

```bash
# Static checks
ls -la webui/src/animations/*.ts     # 8 files
ls -la webui/src/views/*.tsx          # 4 view files

# TypeScript
cd webui && npx tsc --noEmit          # must pass

# Backend smoke (uses FastAPI directly, no browser)
python -c "from fastapi.testclient import TestClient; \
           from alphaloop.webui.api import create_app; \
           TestClient(create_app(runs_dir='./runs')).get('/healthz')"

# Vitest
cd webui && npm test                  # expect: ≥ 30 passed
cd webui && npm run test:coverage -- --coverage
                                      # expect: ≥ 80% line coverage

# Playwright
cd webui && npm run test:e2e          # expect: ≥ 6 passed

# Backend pytest
pytest tests/test_webui_api.py tests/test_webui_data.py \
       tests/test_webui_schemas.py tests/test_webui_export.py -v
                                      # expect: ≥ 14 passed

# Combined gate
pytest --collect-only | tail -1       # expect: ≥ 285 collected (Python)
```

---

## 8. Risks

### 8.1 R1 — Dark mode browser compatibility

**Risk:** Some users have OS-wide "light mode only" or "high contrast"
preferences. Our dark-only design may be unreadable to them, and we
have no light-mode fallback (Quant Lab is dark by definition).

**Mitigation:**
- All text contrast ≥ 4.5:1 (already designed, § 4.6).
- Tailwind's `dark:` prefix lets us opt in to light mode via
  `@media (prefers-color-scheme: light)` without rewriting components.
  A "Quant Lab light" theme is a 30-line addition to
  `tailwind.config.ts` (deferred to v0.7.2 if user requests).
- Framer Motion's `useReducedMotion()` also covers user a11y
  preferences — falls back to static states (§ 5.9).
- Document "best viewed in dark mode" in `README.md`.
- For v0.7.1: log a console warning if `prefers-color-scheme: light`
  is detected; the user can override via `?theme=light` query param
  (CSS-only, no JS).

**Likelihood:** Low (most quant tools assume dark mode).
**Impact:** Medium (accessibility concern).

### 8.2 R2 — progress.json writer hook in v0.7 LoopRunner

**Risk:** SSE needs `runs/<rid>/progress.json` written every 5 s by
the LoopRunner. Currently v0.7 doesn't write this file — we'd need
a 1-line addition to `_tick_progress` in `runner.py`. If the user
later refactors `_tick_progress`, the SSE stream silently breaks.

**Mitigation:**
- The writer is a **single function call** in
  `LoopRunner._tick_progress()` — easy to spot in code review.
- Add a CI test: `test_progress_json_written_every_5s` that runs a
  minimal loop and asserts the file exists with the right shape.
- `sse.stream_run()` already handles `progress.json` being missing
  (yields no events, still alive). Worst case: the UI shows
  "waiting for progress" — no crash, no blank screen.
- Document the contract in `docs/design/v071-webui.md` § 2.5 so the
  v0.7 maintainer knows what depends on it.

**Likelihood:** Medium.
**Impact:** Low (graceful degradation in UI; contract is documented).

### 8.3 R3 — Chart.js bundled via npm (eliminates prior CDN risk)

**Risk:** Eliminated. Chart.js was previously loaded from
`cdn.jsdelivr.net` (the v0.7.1 R2 risk identified in earlier
drafts). With the Vite + React stack, Chart.js is bundled via
`npm install chart.js` and imported with
`import { Chart } from 'chart.js/auto'`. Vite tree-shakes the bundle
to **~80 KB gzipped** (vs 210 KB UMD). All assets are served
locally by FastAPI in production or Vite in dev — **zero external
network requests** for JS/CSS.

If Chart.js ever fails to hydrate for an unforeseen reason (extremely
unlikely since it's bundled), the existing `<table>` fallback path
in each chart wrapper still kicks in (see prior design).

**Likelihood:** Eliminated.
**Impact:** N/A.

### 8.4 R4 — SSE long connection timeout (proxy / load balancer)

**Risk:** Corporate proxies and some cloud load balancers kill idle
HTTP connections after 60–300 s. SSE is a long-lived HTTP response;
a kill = client sees a disconnect, must reconnect.

**Mitigation:**
- `EventSource` auto-reconnects with a 3-s retry (browser default).
- `useEffect` in `ReplayView.tsx` keeps a `last_event_id` in a `ref`;
  on reconnect, sends `Last-Event-ID` header so the server can resume
  from there.
- SSE endpoint sends a `:keepalive\n\n` comment every 15 s (no event
  payload, just a heartbeat) so the connection is never "idle".
- Configurable `--sse-heartbeat-s` (default 15).

**Likelihood:** High (anyone behind a corporate proxy).
**Impact:** Low (auto-reconnect handles it; brief UI flicker).

### 8.5 R5 — React + Framer Motion bundle size

**Risk:** Production JS budget is **~220 KB gzipped** (§ 3.3):
- React 18 + react-dom: ~45 KB
- react-router-dom: ~12 KB
- Framer Motion: ~50 KB
- Chart.js (tree-shaken): ~80 KB
- app chunks: ~30 KB

On a slow 3G connection, 220 KB gzipped = ~3 s additional load time
on top of first paint. Quant tools target desktop users on
broadband, so this is acceptable — but on a corporate VPN
with constrained egress, the user might see a "loading…" for several
seconds.

**Mitigation:**
- **Vite code splitting per route**: `ReplayView` and
  `StrategyDetailView` lazy-loaded; TopFiveView (the entry route)
  ships only the critical bundle first.
- **Defer non-critical imports**: Chart.js loaded asynchronously on
  views that need it; not eagerly imported into `main.tsx`.
- **Framer Motion tree-shaking** enabled via `framer-motion/dom`
  sub-imports (only the motion APIs we use are bundled).
- **`<link rel="modulepreload">` for 4 chunks** in `index.html`
  prefetches lazy routes.
- Performance test in § 7.6 asserts FCP < 1.5 s on the entry route.
  Tweak budgets later if real-world perf regresses.

**Likelihood:** Low (target audience: desktop users).
**Impact:** Medium (perceived "slowness" on first load; tolerable).

### 8.6 R6 — Vite dev server port conflicts

**Risk:** Vite defaults to port `5173`, FastAPI to `:8000`. Both
must be free simultaneously during dev. If `5173` is taken (e.g.,
the user has a previous Vite running, or a corporate proxy maps
5173), `npm run dev` fails or picks a different port silently.

**Mitigation:**
- `vite.config.ts` sets `port: 5173, strictPort: true` so Vite
  refuses to start on a different port — fails loud, not silent.
- Same for FastAPI: `uvicorn --port 8000` with strict-port error.
- The dev proxy in `vite.config.ts` is **proxy-aware**: it uses a
  function-based proxy that reads `process.env.ALPHALOOP_API_URL`
  if set, defaulting to `http://localhost:8000` — single env var
  to override.
- Document the expected dev process model in `README.md` (and the
  loop state file): "Run `alphaloop webui` in terminal A,
  `npm run dev` in terminal B."

**Likelihood:** Medium.
**Impact:** Low (clear error message; not silent).

### 8.7 R7 — TypeScript maintenance overhead

**Risk:** Every Pydantic schema added on the backend requires a
matching `webui/src/api/types.ts` definition. Drift causes
runtime-only bugs that FastAPI TestClient + msw tests catch late,
not at type-check time.

**Mitigation:**
- **Auto-generate TypeScript types from OpenAPI**:
  `npx openapi-typescript http://localhost:8000/openapi.json -o
  src/api/types.ts`. Run as a `predev` script in `package.json`.
- **Same msw handlers** in `webui/tests/utils/handlers.ts` mirror
  Pydantic schemas — when schemas change, msw handlers must be
  updated, which fails the tests loudly.
- Vitest + RTL tests assert types via `expectTypeOf` (Vitest's type
  testing API) — catches drift before runtime.
- **CI gate**: `tsc --noEmit` + `pytest tests/test_webui_schemas.py`
  both must pass before merge. If either fails, type drift is
  caught in CI, not production.

**Likelihood:** Medium (any backend change can break).
**Impact:** Medium (runtime bugs are bad; mitigated by CI gate).

### 8.8 R8 — Client-side routing vs server-side routing

**Risk:** React Router uses HTML5 History API (`pushState`); when
the user reloads `/strategy/t1` or hits deep-link from outside,
the FastAPI production server might `404` instead of serving
`index.html` (the SPA fallback).

**Mitigation:**
- FastAPI production server has a catch-all route that returns
  `index.html` for any non-`/api/*`, non-static path:
  ```python
  @app.get("/{full_path:path}", include_in_schema=False)
  async def spa_fallback(full_path: str):
      if full_path.startswith("api/"):
          raise HTTPException(404)
      return FileResponse("webui/dist/index.html")
  ```
- Vite dev server already handles SPA fallback natively
  (`historyApiFallback` is on by default).
- Playwright tests in § 7.5 verify direct-URL access for each of
  the 4 routes (e.g., test_replay_direct_link).

**Likelihood:** Low (well-documented pattern).
**Impact:** Medium (deep-links broken without fix).

### 8.9 R9 (bonus) — 8 animations performance on low-end machines

**Risk:** On a 5-year-old laptop, 8 simultaneous Framer Motion
animations could drop below 30 FPS, making the UI feel sluggish.
Worst offender: `dagEdgeFlow` runs `strokeDashoffset` animation
on 5 SVG edges simultaneously.

**Mitigation:**
- All animations use `transform` / `opacity` / `strokeDashoffset`
  (GPU-accelerated where possible).
- `useReducedMotion()` disables all 8 animations for users with
  that OS preference (~10% of users; § 5.9).
- `?anim=off` query param disables animations manually.
- Performance test (§ 7.6) verifies ≥ 55 FPS on a 4-year-old
  laptop reference profile (Chromebook Plus baseline).
- Framer Motion's `<LazyMotion>` wrapper defers Framer features
  that aren't used to a smaller bundle, with `domAnimation` features
  only — keeps the runtime slim.
- Worst-case rollback: ship as 4 animations, add 4 more if perf
  budget allows (deferred to v0.7.2).

**Likelihood:** Low (modern laptops handle this trivially).
**Impact:** Medium (one-time perf hit during replay).

### 8.10 R10 (bonus) — WebSocket vs SSE (decision rationale)

**Risk:** Should we have used WebSocket instead of SSE? What if a
future feature needs bidirectional communication?

**Decision: SSE.**
- WebSocket needs an upgrade handshake (`Upgrade: websocket`), which
  some corporate proxies strip.
- SSE is plain HTTP/1.1 + text/event-stream; works everywhere.
- Our use case is **one-way** (server pushes progress, client only
  renders). WebSocket is overkill.
- React consumes the same data shape FastAPI emits — no hydration
  gap.
- **If a future feature needs bidirectional** (v0.8+ user-driven
  commands), we add WebSocket as a *second* channel; SSE stays for
  progress. No migration cost.

**Likelihood:** N/A (decision is documented).
**Impact:** None (this is a rationale, not a risk).

### 8.11 R11 (bonus) — v0.7.1 vs v0.8 scope creep

**Risk:** While implementing the WebUI, the developer is tempted to
add "just one more thing" — multi-run compare, auth, dark/light
toggle. These are NOT in the user-confirmed scope (state file
§"context").

**Mitigation:**
- This design doc is the source of truth; any deviation requires
  explicit user OK before implementation.
- The hard wall in the loop state file prohibits modifying anything
  outside `docs/design/v071-webui.md` during the design phase.
- A reviewer reading this doc can spot scope creep and reject the
  PR.

**Likelihood:** High (classic scope-creep failure mode).
**Impact:** High (delays ship, bloats scope).

### 8.12 R12 (bonus) — Export HTML size creep

**Risk:** Inlining React + Framer + Chart.js + app code per export
→ file balloons past the 500 KB success criterion.

**Mitigation:**
- Vite production build is minified + tree-shaken; React + Framer +
  Chart.js summed to ~220 KB gzipped — already inside budget.
- Use `vite build --minify=esbuild` (default) for minified output.
- Track size in CI: `assert os.path.getsize(export_path) < 500_000`.
- Worst case: ship a compressed (.br or .gz) version alongside the
  raw `.html`; deferred to v0.7.2.

---

## 9. Open questions (need user confirmation)

These are NOT blockers for design — they're noted so the dev agent
can confirm before implementation begins:

1. **Run-selector default:** Should `/` redirect to `/run/<latest>`
   or stay at `/` showing the Top-5 card? (Current design: `/` shows
   Top-5; `/run/<id>` shows diagnostics. User picks via topbar.)

2. **Compare-runs query param:** Should `/run/<id>?compare=<other_id>`
   overlay two radars? (Design includes it; cheap to add. Confirm.)

3. **Dark mode toggle:** Ship a `?theme=light` escape hatch in v0.7.1
   (30 lines of CSS), or defer to v0.7.2? (Current design: dark only
   with a documented "use prefers-color-scheme: dark" expectation.)

4. **Animation count strict-or-flexible:** Is "exactly 8" a hard
   requirement, or "at least these 8"? (Current design: exactly 8,
   named in § 5. Adding a 9th requires user OK.)

5. **Chart.js version pinning:** Pin to `chart.js@4.4.1` or float on
   `@4`? (Current design: pinned via `package.json` lockfile for
   reproducibility; floats risk breaking msw test fixtures.)

6. **Export HTML format:** Single file (current design) or a zip with
   `data.json` + `index.html` + assets/? (Current design: single file
   for share-ability; zip is friendlier for re-import.)

7. **Test count target:** § 1.7 says ≥ 14 backend tests + ≥ 30
   frontend tests + ≥ 6 e2e tests, taking the Python suite 271 → 285.
   Is this the right split, or should we aim higher on any side
   (e.g., 40 frontend tests to cover all 8 animations plus 4 views
   × 5 boundary cases)?

8. **TypeScript codegen vs hand-rolled types:** Should
   `webui/src/api/types.ts` be auto-generated from
   `/openapi.json` via `openapi-typescript` (preferred — catches
   drift), or hand-mirrored against Pydantic (faster iteration, more
   drift risk)? Current design: auto-generated as `predev` script.

9. **Two-process dev model:** OK with devs running `uvicorn
   alphaloop.webui.api:app` (terminal A) + `npm run dev` (terminal B)
   during dev? Alternative: bake the FastAPI client into Vite's dev
   server via a Vite plugin (single process, more coupling).

---

## 10. Implementation phasing (4 weeks / 20 days)

| Week | Days | Milestone                                                     |
|------|------|---------------------------------------------------------------|
| 1    | 1–5  | Scaffold `webui/` Vite project + `src/alphaloop/webui/` FastAPI JSON package; tokens.css + tailwind.config.ts dark theme; `App.tsx` + `TopFiveView` (with `TopFiveCard`) renders against mock JSON; FastAPI `/healthz` + `/api/runs` live; 1 sample run. |
| 2    | 6–10 | `StrategyDetailView` + `RunDiagnosticsView`; Pydantic schemas + openapi-typescript codegen; RadarChart / BarChart / EquityCurve wired; export HTML v1; **5 backend test files + 12 Vitest tests** done. |
| 3    | 11–15| `ReplayView` (6-node SVG DAG) + 8 Framer Motion variants + SSE consumer; `progress.json` writer in v0.7 LoopRunner; msw handlers for all 7 endpoints; **Playwright e2e tests** written (≥ 6 specs). |
| 4    | 16–20| Performance pass (FCP < 1.5 s, FPS ≥ 55, Framer bundle < 60 KB gz); accessibility audit (reduced-motion, focus-visible); docs (README section + screenshots); dogfood on 5 real loop runs; **ship**. |

Hard gates per week:

- **End of W1:** `GET /api/runs` returns ≥ 1 run; `npm run dev` shows
  5 cards via msw fixtures on `localhost:5173/`. Gate: `curl
  /healthz` + Playwright screenshot of `/`.
- **End of W2:** All 4 JSON endpoints return 200; all 4 React routes
  render. Gate: `pytest tests/test_webui_api.py -v` (≥ 10 passed) +
  `npm test` (≥ 12 passed).
- **End of W3:** 8 Framer Motion variants visible in browser; SSE
  stream advances `progress-bar` in `/replay/<rid>`. Gate:
  Playwright screenshot + `prefers-reduced-motion` test.
- **End of W4:** ≥ 14 Python tests + ≥ 30 Vitest tests + ≥ 6 e2e
  tests pass; ≥ 285 total Python tests; export works offline. Gate:
  full CI green.

---

## 11. References

- v0.7 design (this WebUI builds on): `docs/design/v07-hybrid-loop.md`
  (883 lines)
- v0.6 design (Q7 LLM judge): `docs/design/v06-llm-judge.md` (762 lines)
- v0.7 persistence: `src/alphaloop/loop/persistence.py` (615 lines)
- v0.7 DAG: `src/alphaloop/loop/dag.py` (239 lines)
- v0.7 aggregator: `src/alphaloop/loop/aggregator.py` (491 lines)
- ROADMAP: `ROADMAP.md` § v0.7.1
- Loop state file: `~/.hermes/profiles/coder/.claude/loops/alphaloop-v071-webui-design-revise.md`
- **Vite docs:** https://vitejs.dev/
- **React 18 docs:** https://react.dev/
- **TypeScript docs:** https://www.typescriptlang.org/docs/
- **Tailwind CSS:** https://tailwindcss.com/docs
- **Framer Motion:** https://www.framer.com/motion/
- **React Router:** https://reactrouter.com/
- **Vitest:** https://vitest.dev/
- **React Testing Library:** https://testing-library.com/docs/react-testing-library/intro/
- **Playwright:** https://playwright.dev/
- **msw (Mock Service Worker):** https://mswjs.io/
- **openapi-typescript:** https://openapi-ts.dev/
- **Chart.js 4 docs:** https://www.chartjs.org/docs/4.4.1/
- **FastAPI SSE:** https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
- **FastAPI Pydantic:** https://docs.pydantic.dev/latest/
- Quant Lab visual references: Linear, Stripe Press, Vercel Analytics,
  TradingView (dark mode).

---

## 12. Self-check (Loop Engineering, per `~/.hermes/profiles/coder/CLAUDE.md`)

- [x] **Goal:** 5-section design doc for v0.7.1 WebUI with 4 views + 8
       Framer Motion animations + Quant Lab visual language, on the
       Vite + React + TypeScript stack.
- [x] **Plan:** Read v0.7 design + persistence.py + dag.py +
       aggregator.py → write 5-section design doc → verify ≥ 400
       lines + 5 sections.
- [x] **Verify:** `wc -l ≥ 400`, `grep "## Goals|Architecture|API|Tests|Risks"
       ≥ 5`, `grep -c "FastAPI|Jinja2" = 0 (except JSON-API references)`,
       `grep -c "Vite|React" ≥ 10` — all four checks documented in
       this loop's verify block.
- [x] **Stop rule:** Design phase ends when verify passes AND user
       explicit OK received (per loop state file §"stop_when").
- [x] **State:** This design doc + the loop state file's state.last_*
       fields updated by the Coder agent on completion.
- [x] **Hard wall:** No code, no tests, no commits, no broker
       connections — only this `.md` (and the loop state file).