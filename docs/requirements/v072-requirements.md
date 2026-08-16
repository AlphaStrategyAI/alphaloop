---
title: "alphaloop v0.7.2 — Requirements (PRD)"
version: "0.7.2"
status: "requirements"
authors:
  - alphaloop Coder subagent
date: "2026-08-16"
loop: "alphaloop-v072-requirements-doc"
related_roadmap_section: "ROADMAP.md § v0.7.2"
supersedes: "none — v0.7.2 ships on top of v0.7.1"
---

# alphaloop v0.7.2 — Product Requirements (PRD)

## 0. Context

alphaloop v0.7.1 (commit `facef25`, tag `v0.7.1`) shipped the WebUI
read-mostly Vite + React + TypeScript SPA with 4 views (Top-5 card,
Strategy Detail, Run Diagnostics, Replay), 8 Framer Motion animations,
and a dark "Quant Lab" visual language. v0.7.1 design doc
(`docs/design/v071-webui.md`, 2045 lines) is the source of truth for
the implementation; this PRD is the requirements layer for v0.7.2.

v0.7.2 scope was confirmed by the user as **E1 — polish + auto-launch
+ docs 起步** with an explicit addition: **share link** so the top-5
view is shareable. v0.7.2 does NOT introduce a new view, a new
diagnostic, or a new LLM feature. It hardens v0.7.1 so that:

1. After `alphaloop loop "..."` finishes, the user lands on the
   results in their browser automatically — no copy-paste of a URL.
2. The top-5 view can be shared with a single click as a stable URL.
3. The WebUI is more usable (dark/light toggle, keyboard shortcuts,
   screenshot capture) without rebuilding the whole UI.
4. The project gets its first usable documentation site.

This PRD is **requirements only**. It contains NO implementation
code, NO test code, NO design diagrams beyond ASCII. Per the loop
state file, implementation is gated on user explicit OK after this
PRD is reviewed.

Hard wall (per loop state file §"需求阶段 hard wall"):

1. Only write this requirements doc; no code, no tests, no design.
2. Do not modify any existing alphaloop file except by *creating*
   `docs/requirements/v072-requirements.md`.
3. Do not write `src/alphaloop/webui/*` (deferred to v0.7.2 dev).
4. Do not write `webui/src/*` or `webui/package.json` (deferred).
5. Do not write `tests/test_webui.py` or `tests/webui/*` (deferred).
6. No commits, no pushes, no broker connections, no auth services.

---

## 1. Goals

v0.7.2 has **4 primary goals** and **1 stretch goal**. Each goal is
phrased in user-facing language so reviewers can sanity-check
scope without reading requirements prose.

### Goal 1 — Auto-launch the WebUI after a loop run finishes

After `alphaloop loop "<goal>"` returns, the user's default browser
opens to `http://127.0.0.1:5173/` (or a similar local URL)
displaying the top-5 view for the just-completed run. Today the
user has to manually start `uvicorn` + `npm run dev` and paste the
URL into a browser. v0.7.2 collapses those two terminal windows
into a single command.

### Goal 2 — Share link for the top-5 view

A single click on the top-5 view produces a URL of the form
`https://alphaloop.example/s/<run_id>` (or a token-protected variant)
that anyone can open in a browser to see the top-5 + 7 diagnostics
+ key charts. The share link is read-only: viewers cannot edit,
rerun, or delete the run. v0.7.1 already produces a self-contained
HTML export (`src/alphaloop/webui/export.py`); the share link
builds on that same export surface and is the natural extension.

### Goal 3 — WebUI polish (dark/light, keyboard, screenshot)

The v0.7.1 dark "Quant Lab" theme is the design default. v0.7.2
adds a one-click light theme escape hatch, a small set of keyboard
shortcuts (1–4 to switch views, `r` to rerun, `?` for help), and a
screenshot button that downloads the current view as a PNG. These
are small surface-area polish items; they reuse existing components
and do not require a redesign.

### Goal 4 — Documentation site (起步)

alphaloop has grown to ~7,000 lines of Python + ~3,000 lines of
TypeScript across 11 strategies, 10 factors, 6+1 diagnostics, an
LLM judge, a hybrid loop, and a WebUI. There is no central place
to find this. v0.7.2 ships a **minimal documentation site** (one
landing page + a getting-started page + an API/CLI reference
generated from argparse help) hosted on GitHub Pages under
`AlphaStrategyAI.github.io/alphaloop/`. Full multi-page docs
(中文版, tutorials, theme customization, plugin authoring) are
explicitly deferred to v1.0.

### Stretch Goal 5 — Optional: share link analytics

If the timeline allows, the share-link endpoint records a
view counter per `run_id` so the loop author can see how many
people opened the shared top-5. This is a **single counter per
run**; no per-viewer analytics, no IP logs, no third-party tracker.
Defer to v0.7.3 if it threatens Goal 1–4.

---

## 2. Requirements

Each requirement is written as a **user story** in the canonical
form: "As a [user], I want to [action], so that [benefit]." After
each story is a **detail block** that names the underlying
behavior, the inputs and outputs, and any constraints the
implementation must respect. Acceptance criteria are in § 3.

The 12 user stories below are grouped by feature: **R-AutoLaunch**
(stories 1–3), **R-ShareLink** (stories 4–7), **R-Polish**
(stories 8–10), **R-Docs** (story 11), **R-CrossCutting**
(story 12).

### R-AutoLaunch — Auto-launch the WebUI after `alphaloop loop`

#### Story 1 — Auto-launch on loop completion

> **As a quant researcher**, I want to run
> `alphaloop loop "find alpha with DSR > 1.0"`, and when it finishes
> **automatically** have my browser open to the top-5 view for
> that run, so that I do not have to copy-paste URLs or start
> two terminals manually.

**Detail.**

- Trigger: `LoopRunner.run()` returns successfully (exit code 0).
- Action: CLI spawns a child process running
  `alphaloop.webui.api:create_app` on a free local port (see Story 3
  for fallback), then opens the URL
  `http://127.0.0.1:<port>/run/<run_id>` (or `/` if the user
  prefers; configurable, default `/run/<run_id>`).
- Mechanism: Python's stdlib `webbrowser.open(url, new=2)` opens a
  new tab in the user's default browser. `new=2` (new window) is
  preferred over `new=1` (new tab) because users may have unrelated
  tabs they want to keep open.
- Browser selection: `webbrowser` respects the `BROWSER` env var
  on Linux and the default-app setting on macOS / Windows.
- Server lifecycle: the FastAPI server runs as a child process of
  the CLI; it is killed when the CLI process exits (so closing
  the terminal tab kills the server). The implementation must use
  `subprocess.Popen(...)` + `atexit.register(server.terminate)`
  so that Ctrl-C of the CLI also kills the server.
- Timeout: the server has no built-in idle timeout in v0.7.2. The
  user can stop it with Ctrl-C in the terminal or
  `lsof -ti:5173 | xargs kill` (documented in the loop subcommand
  help text).

#### Story 2 — Skip auto-launch via `--no-launch` flag

> **As a quant researcher running alphaloop on a remote server
> without a desktop**, I want to pass `--no-launch` to
> `alphaloop loop` so that the CLI does not try to open a browser,
> so that my long-running batch job does not hang or fail on a
> headless box.

**Detail.**

- New CLI flag on the `alphaloop loop run` subcommand (and the
  default `alphaloop loop "<goal>"` form):
  `--no-launch` (default: False, i.e. auto-launch on).
- When `--no-launch` is set, the loop runs to completion, prints
  the artifact path as today, and exits without spawning a server
  or calling `webbrowser.open`.
- When `--no-launch` is NOT set but `$DISPLAY` (Linux) or
  `$SSH_TTY` is unset (headless heuristic), the CLI prints a
  warning to stderr: `warning: no display detected, falling back
  to --no-launch` and behaves as if `--no-launch` was passed.
  The heuristic is best-effort; users on weird WSL / X-server
  setups may still need to set `--no-launch` explicitly.

#### Story 3 — Port conflict fallback

> **As a quant researcher who already has a `5173` Vite dev
> server running from a previous session**, I want
> `alphaloop loop` to **transparently** pick the next free port
> (5174, 5175, …) instead of failing, so that I do not have to
  kill the orphan process manually.

**Detail.**

- Port range: try `5173` first, then `5174`, `5175`, … up to a
  hard cap of `5183` (10 attempts).
- Mechanism: bind a TCP socket to `127.0.0.1:<port>` with
  `SO_REUSEADDR`; if `bind()` succeeds, close the socket and use
  that port. If all 10 attempts fail, fall back to a random
  ephemeral port in the OS-assigned range and log the chosen port.
- The CLI prints the chosen port to stdout (so the user can copy
  it if the browser fails to open):
  `alphaloop webui serving on http://127.0.0.1:5176/`.
- The chosen port is also written to
  `runs/<run_id>/.webui-port` so a future iteration can offer
  "open last run" UX without re-scanning.

### R-ShareLink — Shareable top-5 URL

#### Story 4 — One-click share link generation

> **As a quant researcher who just got a great top-5**, I want to
> click a **"Share"** button on the top-5 view and get a URL that
> I can paste into Slack or email, so that I can send my result
> to a colleague without exporting a file.

**Detail.**

- UI: a "Share" button on the TopFiveView, next to the existing
  "Run diagnostics →", "Replay DAG →", "Export HTML" buttons.
- On click: the frontend calls `POST /api/runs/<rid>/share` (new
  endpoint), receives a JSON `{ "url": "...", "expires_at": "..." }`,
  and copies the URL to the clipboard via
  `navigator.clipboard.writeText(url)`. A toast confirms
  "Copied: https://…".
- Backend: `POST /api/runs/<rid>/share` mints a share token
  (UUID4, URL-safe base64-encoded) and stores it in
  `runs/<rid>/.share.json` (or a small `shares.db` SQLite file if
  multiple links per run are needed — see Story 7). The endpoint
  returns `https://alphaloop.example/s/<token>` as the URL.
  The `alphaloop.example` host is configurable via env var
  `ALPHALOOP_SHARE_BASE_URL`; default for v0.7.2 is
  `http://127.0.0.1:<port>` (i.e. local dev only).
- Read-only guarantee: the share URL only resolves via
  `GET /s/<token>` which is documented in Story 5. There is no
  share-side mutation endpoint.
- Note: the public domain `alphaloop.example` is a placeholder.
  v0.7.2 ships the local-only default; a real public host is
  post-v1.0.

#### Story 5 — Share link renders top-5 + diagnostics + key charts

> **As a colleague who received a shared link**, I want to open
> the URL in my browser and see the **same 5 cards + 7-diagnostic
> radar + key charts** that the loop author saw, so that I can
> evaluate the result without installing alphaloop or asking for
> a file.

**Detail.**

- Frontend route: `/s/<token>` (new React Router route).
- On load: `GET /api/share/<token>` returns the same JSON shape
  as `GET /api/runs/<rid>/top5` + `GET /api/runs/<rid>/diagnostics`,
  but scoped to the token (no `rid` exposed if the user prefers
  privacy, see Story 7).
- The view renders the TopFiveCard grid (5 cards) + the 3-axis
  radar + the strategy-equity curve (one card, not all 5 — keep
  the share page under 1 MB transferred).
- The view is **read-only**: no rerun button, no export-to-edit,
  no share-this-link (preventing share-of-share infinite loop).
- The view shows a small footer: "Shared via alphaloop v0.7.2.
  Read-only snapshot." with a link to the project.
- No backend server is required if the implementation reuses the
  v0.7.1 export pattern: the share endpoint can produce a
  self-contained `.html` (using `build_export_html`) and serve it
  at `/s/<token>` as `text/html`. v0.7.2 chooses this path for
  simplicity (no need to keep a backend running to view a shared
  link).

#### Story 6 — Share link longevity (≥ 30 days)

> **As a quant researcher who shared a link with my team two
> weeks ago**, I want to re-share the same URL a month later and
> still have it resolve, so that I do not have to regenerate
> share links every time someone asks about an old run.

**Detail.**

- Default TTL: 30 days from creation. Configurable via
  `POST /api/runs/<rid>/share?ttl-days=NN` (capped at 365).
- Persistence: share tokens + their run_id + their expiry live in
  `runs/<rid>/.share.json` (one JSON file per run, append-only
  history) OR in a single `~/.alphaloop/shares.json` (cross-run).
  v0.7.2 picks the per-run file for symmetry with the rest of
  `runs/`.
- Expiry check: `GET /api/share/<token>` returns 404 + a clear
  JSON `{"error": "share link expired"}` once `expires_at < now`.
- The expiry is **soft**: the run artifacts stay on disk; only
  the share token is invalidated. Re-sharing creates a new token.
- Test: `test_share_link_ttl_30_days` asserts that a token
  created with `ttl-days=30` is resolvable on day 0 and not on
  day 31 (using `freezegun` or `time-machine`).

#### Story 7 — Share link privacy (private vs public)

> **As a quant researcher sharing with a small team**, I want
> share links to be **unlisted-by-default** (anyone with the URL
> can view) but with an optional **token-in-URL** mode so that I
> can rotate the token if it leaks, so that my runs are not
> world-indexable.

**Detail.**

- Default mode: **unlisted**. URL is
  `https://alphaloop.example/s/<long_random_token>`. There is no
  index page; search engines and alphaloop itself do not list
  share links.
- Optional: **rotatable token**. The CLI subcommand
  `alphaloop share rotate --run-id <rid>` mints a new token,
  revokes the old one, and prints the new URL. Old URL returns
  410 Gone.
- NOT implemented in v0.7.2 (deferred to v0.7.3 if needed): a
  **password-protected** mode where the URL is
  `https://alphaloop.example/s/<token>` and the viewer must enter
  a passphrase. Reasoning: v0.7.2 is local-dev only
  (`127.0.0.1`), so a password adds little value. If v0.7.2+1
  ships a public host, password mode becomes Goal 4 of that
  release.

### R-Polish — WebUI polish (dark/light, keyboard, screenshot)

#### Story 8 — Dark/light theme toggle

> **As a quant researcher working in a bright room**, I want a
> **sun/moon button** in the top-right corner of the WebUI that
> toggles between dark ("Quant Lab") and a light theme, so that
> I am not blinded by a dark-on-light clash with my environment.

**Detail.**

- UI: a `🌙 / ☀` button in the TopFiveView topbar (next to the
  run selector) and on every other view's topbar.
- On click: the frontend toggles `data-theme="light"` on
  `<html>`; the CSS rules under `:root[data-theme="light"]` (a
  v0.7.2 addition to `webui/src/styles/tokens.css`) override
  the dark-mode defaults.
- Persistence: the choice is saved to `localStorage["alphaloop.theme"]`
  and restored on next page load.
- `prefers-color-scheme: light` users get light mode by default
  (today they get dark, which is the v0.7.1 R1 risk).
- Reduced-motion / high-contrast users keep the dark default
  (their OS preference is already authoritative; we do not
  override accessibility choices).
- The toggle is **not** a third theme. v0.7.2 ships dark +
  light; custom themes are post-v1.0.

#### Story 9 — Keyboard shortcuts (1–4, r, ?)

> **As a quant researcher who lives in the keyboard**, I want to
> press `1`–`4` to switch between the 4 views, `r` to rerun the
> current run, and `?` to show a help overlay, so that I never
> have to leave the keyboard.

**Detail.**

- Bindings (global, ignored when typing in an `<input>`):
  | Key | Action                                      |
  |-----|---------------------------------------------|
  | `1` | Navigate to `/` (Top-5)                     |
  | `2` | Navigate to `/run/<rid>` (Diagnostics)      |
  | `3` | Navigate to `/replay/<rid>` (Replay DAG)    |
  | `4` | Navigate to `/strategy/<sid>?rid=<rid>`     |
  | `r` | `POST /api/runs/<rid>/replay` and reload    |
  | `?` | Toggle the keyboard-shortcut help overlay   |
  | `Esc` | Close any open modal / overlay            |
- Implementation: a single `useEffect` in `App.tsx` that
  attaches a `keydown` listener to `window` and dispatches
  via `react-router`'s `useNavigate` + `apiClient.replay`.
- The help overlay (`?`) lists all bindings in a small
  centered card with a backdrop. `Esc` closes it.
- `r` is **gated on user confirmation**: a confirmation modal
  "Rerun <run_id>? This will re-execute the DAG." with
  `Enter` = yes, `Esc` = no. This prevents accidental reruns.
- The shortcut hints are also listed in the README "Keyboard
  shortcuts" section (so users can discover them without
  pressing `?`).

#### Story 10 — Screenshot capture (PNG download)

> **As a quant researcher preparing a slide deck**, I want to
> click a button and download a **PNG screenshot** of the
> current view, so that I can drop it into Keynote / PowerPoint
> without taking a manual OS screenshot.

**Detail.**

- UI: a 📷 button in each view's topbar.
- On click: the frontend uses `html2canvas` (already in
  `package.json` from v0.7.1's export path) to render the
  visible `<main>` element to a canvas, then exports the canvas
  as `image/png` via `canvas.toBlob` and triggers a download
  with filename `alphaloop-<view>-<rid>-<timestamp>.png`.
- The screenshot is **only the current view**, not the whole
  page (toolbar / footer are excluded).
- The button has a brief "Capturing…" state (≤ 1 s for typical
  views) so the user knows something is happening.
- If `html2canvas` fails (very rare; it's bundled), the button
  falls back to the v0.7.1 "Export HTML" path with a toast:
  "Screenshot failed; HTML export ready."
- Bundle-size impact: `html2canvas` is ~40 KB gzipped. v0.7.1
  total budget was 220 KB; v0.7.2 budget is 260 KB. The
  performance test (§ 3.4) asserts FCP < 1.5 s still holds.

### R-Docs — Documentation site (起步)

#### Story 11 — Minimal docs site (GitHub Pages)

> **As a new user who just installed `pip install alphaloop`**, I
> want to visit a docs site and find (a) what alphaloop is,
> (b) how to run my first `alphaloop loop`, (c) the CLI reference,
> so that I can go from zero to first run without reading the
> source code.

**Detail.**

- Host: GitHub Pages under
  `https://AlphaStrategyAI.github.io/alphaloop/`. The repo
  `AlphaStrategyAI/alphaloop` already has Pages enabled (v0.7
  shipped the workflow hook); v0.7.2 adds the docs source.
- Source: `docs-site/` directory at repo root (separate from
  `docs/` which holds design docs / retrospectives). The site
  is a plain static site generated by **MkDocs** with the
  **Material theme** — both are stdlib-Python-friendly, no
  Node build step needed for docs.
- Pages in v0.7.2 (3 total, intentionally tiny):
  1. `index.md` — "What is alphaloop?" + 3-paragraph pitch +
     "Quick start" code block.
  2. `getting-started.md` — install, first `alphaloop loop`
     walkthrough with screenshot, how to launch the WebUI.
  3. `reference.md` — full CLI reference, auto-generated from
     `argparse` help via a `scripts/gen_cli_reference.py` step.
- NOT in v0.7.2 (explicitly deferred): tutorials, 中文版,
  architecture diagrams, plugin authoring guide, theme
  customization. These go to v1.0.
- CI: a new workflow `.github/workflows/docs.yml` builds the
  MkDocs site on every push to `main` and deploys to Pages.
  Failure of this workflow does NOT block PR merge (it's a
  separate job).

### R-CrossCutting — Test & quality bar

#### Story 12 — Tests cover all v0.7.2 features

> **As the maintainer of alphaloop**, I want **automated tests**
> for every v0.7.2 feature, so that v0.7.3 can refactor without
> breaking user-visible behavior.

**Detail.**

- Python tests (pytest):
  - `tests/test_cli_auto_launch.py` (≥ 4 tests): auto-launch
    happy path, `--no-launch`, port fallback, headless detection.
  - `tests/test_share_link.py` (≥ 6 tests): mint + resolve, TTL
    expiry, token rotation, share endpoint 404 cases.
  - `tests/test_docs_build.py` (≥ 2 tests): MkDocs config valid,
    generated reference.md matches argparse help.
- TypeScript tests (Vitest + RTL):
  - `webui/tests/views/ThemeToggle.test.tsx` (≥ 3 tests).
  - `webui/tests/views/KeyboardShortcuts.test.tsx` (≥ 4 tests).
  - `webui/tests/views/ScreenshotButton.test.tsx` (≥ 2 tests).
- E2E tests (Playwright):
  - `webui/tests/e2e/auto_launch.spec.ts` (≥ 1 test): stub
    `webbrowser.open`, run a mini-loop, assert the URL was
    opened with the expected host:port.
  - `webui/tests/e2e/share_link.spec.ts` (≥ 2 tests): create
    share, fetch `/s/<token>`, assert top-5 visible.
- Coverage target: ≥ 80 % on the new Python files, ≥ 70 %
  on the new TypeScript files. The existing v0.7.1 baseline
  (≥ 285 Python tests, ≥ 30 Vitest tests, ≥ 6 e2e tests) must
  continue to pass.

---

## 3. Acceptance Criteria

Each acceptance criterion is a **single, observable check** that
a reviewer can perform by running one command or one test. The
criteria are grouped by feature; each criterion maps back to one
or more stories in § 2.

### 3.1 Auto-launch (Stories 1–3)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-1.1 | `pytest tests/test_cli_auto_launch.py::test_auto_launch_opens_browser` passes.                           |
| A-1.2 | `pytest tests/test_cli_auto_launch.py::test_no_launch_flag_skips_browser` passes.                        |
| A-1.3 | `pytest tests/test_cli_auto_launch.py::test_port_fallback_5173_to_5174` passes (uses `socket.bind`).     |
| A-1.4 | Manual: running `alphaloop loop "demo"` on a desktop opens a browser to the top-5 view within 5 s of the CLI returning. |
| A-1.5 | Manual: `alphaloop loop --no-launch "demo"` does NOT open a browser and does NOT print any browser-related errors. |
| A-1.6 | Manual: `alphaloop loop "demo"` on a headless box (no `$DISPLAY`) prints the "no display detected" warning and exits 0. |
| A-1.7 | Closing the terminal that ran `alphaloop loop` kills the WebUI server (verified by `curl http://127.0.0.1:<port>/healthz` returning connection refused). |

### 3.2 Share link (Stories 4–7)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-2.1 | `pytest tests/test_share_link.py::test_share_mint_and_resolve` passes.                                   |
| A-2.2 | `pytest tests/test_share_link.py::test_share_ttl_expires` passes (uses `freezegun`).                     |
| A-2.3 | `pytest tests/test_share_link.py::test_share_token_rotation` passes.                                     |
| A-2.4 | `pytest tests/test_share_link.py::test_share_404_for_unknown_token` passes.                              |
| A-2.5 | E2E: `npx playwright test webui/tests/e2e/share_link.spec.ts` passes (≥ 2 specs).                       |
| A-2.6 | Manual: clicking "Share" on a populated top-5 view copies a URL to the clipboard within 2 s and a toast confirms. |
| A-2.7 | Manual: pasting the URL into a fresh browser (no cookies, incognito) opens the top-5 view in under 5 s. |
| A-2.8 | Manual: the share URL contains NO buttons for rerun, edit, or delete — read-only enforced.              |

### 3.3 Polish (Stories 8–10)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-3.1 | `npm test -- ThemeToggle` passes (≥ 3 Vitest tests).                                                     |
| A-3.2 | `npm test -- KeyboardShortcuts` passes (≥ 4 Vitest tests).                                               |
| A-3.3 | `npm test -- ScreenshotButton` passes (≥ 2 Vitest tests).                                                |
| A-3.4 | Visual regression: a Playwright screenshot of `/` in dark mode and in light mode matches the goldens in `webui/tests/golden/` (within 0.1 % pixel diff). |
| A-3.5 | Manual: pressing `1` on `/run/<rid>` navigates to `/` within 500 ms.                                     |
| A-3.6 | Manual: pressing `?` opens the help overlay; `Esc` closes it.                                            |
| A-3.7 | Manual: clicking the 📷 button downloads a PNG named `alphaloop-<view>-<rid>-<ts>.png` within 2 s; opening the PNG in Preview shows the visible view (no scrollbar artifacts). |
| A-3.8 | Bundle-size budget: `webui/dist/assets/*.js` total gzipped ≤ 260 KB (was 220 KB in v0.7.1; +40 KB for `html2canvas`). |
| A-3.9 | Performance: First Contentful Paint < 1.5 s on the entry route (Playwright `performance.timing`).         |

### 3.4 Documentation (Story 11)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-4.1 | `pytest tests/test_docs_build.py::test_mkdocs_config_valid` passes.                                      |
| A-4.2 | `pytest tests/test_docs_build.py::test_cli_reference_matches_argparse` passes (snapshot diff).            |
| A-4.3 | CI: `.github/workflows/docs.yml` runs on push to `main` and deploys to Pages; the workflow's last run shows ✅ green. |
| A-4.4 | Manual: `https://AlphaStrategyAI.github.io/alphaloop/` renders all 3 pages without 404s, broken images, or console errors. |
| A-4.5 | Manual: the `index.md` "Quick start" code block, when copy-pasted into a fresh Python venv on macOS, completes a `alphaloop loop "demo"` run in under 10 minutes. (The "demo" goal is shipped as a fixture in v0.7.2.) |

### 3.5 Cross-cutting (Story 12)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-5.1 | `pytest` total ≥ 285 (v0.7.1 baseline) + 12 new tests = ≥ 297.                                           |
| A-5.2 | `npm test` (Vitest) total ≥ 30 (v0.7.1 baseline) + 9 new tests = ≥ 39.                                   |
| A-5.3 | `npx playwright test` total ≥ 6 (v0.7.1 baseline) + 3 new specs = ≥ 9.                                  |
| A-5.4 | Coverage on new Python files ≥ 80 % (`pytest --cov`).                                                    |
| A-5.5 | Coverage on new TypeScript files ≥ 70 % (`vitest run --coverage`).                                       |
| A-5.6 | CI gate: `pytest`, `npm test`, `npm run test:e2e`, `npm run typecheck`, and `mkdocs build` all pass before merge. |

---

## 4. Out of Scope

The following items are **explicitly NOT part of v0.7.2**. Each
item is listed with a one-line reason and the version it is
expected to land in (if known).

| # | Item                                                | Reason                                                       | Deferred to        |
|---|-----------------------------------------------------|--------------------------------------------------------------|--------------------|
| 1 | **Jupyter / Marimo notebooks**                       | User said "不要 notebooks"                                    | never (out of product) |
| 2 | **Multi-user collaboration** (shared cursors, comments) | Local-dev only; no auth model                                | v2.0 (if at all)   |
| 3 | **New WebUI views** beyond the 4 shipped in v0.7.1  | Scope discipline; v0.7.2 is polish, not feature              | v0.7.3+            |
| 4 | **Full Chinese-language documentation**              | English-only for v0.7.2; translation effort is its own project | v1.0              |
| 5 | **Algolia / DocSearch integration**                  | Docs site is 3 pages; search is overkill                     | v1.0+              |
| 6 | **Custom user themes** beyond dark + light          | 2 themes is enough; more would split design budget           | post-v1.0          |
| 7 | **Mobile-responsive WebUI** (phone-first layout)    | v0.7.1 design target is desktop ≥ 1280 px; tablet works, phone is "readable but ugly" | v0.8 (if users ask) |
| 8 | **WebSocket** transport replacing SSE                 | SSE already shipped; no bidirectional need in v0.7.2         | v0.8+ (if needed)  |
| 9 | **Public share-link hosting** (`alphaloop.com`)      | v0.7.2 is local-only (`127.0.0.1`); public host needs auth, billing, abuse handling | v0.7.3+ or v1.0 |
| 10 | **Password-protected share links**                  | Local-only in v0.7.2; no adversary model yet                  | with public host   |
| 11 | **Landing page redesign / hero animation**           | 起步 docs is intentionally minimal                            | v1.0+              |
| 12 | **Auto-rerun on stale data**                         | Loop is on-demand; auto-rerun is a different product          | never (out of product) |
| 13 | **Plugin / hook system for 3rd-party visualizations** | No 3rd-party plugin interface in v0.7.x                       | v2.0 (if at all)   |
| 14 | **Internationalization** (i18n) of the WebUI         | English-only; UTF-8 strings throughout; no `<Lang>` toggle    | v1.0+              |
| 15 | **Real-time co-editing of share links**              | Multi-user; no auth model                                     | v2.0 (if at all)   |

### Out-of-scope rule (anti-scope-creep)

If during implementation the developer wants to add any item from
this table, they MUST stop and get explicit user OK in writing
(loop state file or chat). The v0.7.2 PR will be rejected if it
contains out-of-scope work.

---

## 5. Dependencies

This section enumerates **external** dependencies (npm, Python,
GitHub Actions, services) that v0.7.2 introduces. Dependencies
already shipped in v0.7.1 are listed once for context.

### 5.1 Python dependencies (pip / `pyproject.toml`)

**New (v0.7.2):**

- `webbrowser` — stdlib, no install needed. Used for opening
  the user's default browser after the loop finishes (Story 1).
- `subprocess` — stdlib, no install needed. Used to spawn the
  FastAPI server as a child process (Story 1).
- `socket` — stdlib, no install needed. Used to probe ports for
  the port-conflict fallback (Story 3).
- `uuid` — stdlib, no install needed. Used to mint share tokens
  (Story 4).
- `secrets` — stdlib, no install needed. Used to mint
  cryptographically random share tokens (Story 4).
- `freezegun` (test-only) — already in v0.7's dev deps, no
  action needed.
- `mkdocs` (≥ 1.5) — new dev dep for the docs site (Story 11).
- `mkdocs-material` (≥ 9.4) — new dev dep for the docs theme.

**Unchanged from v0.7 / v0.7.1:**

- `fastapi` (already required by v0.7.1 WebUI).
- `uvicorn` (already required by v0.7.1 WebUI).
- `pydantic` (already required by v0.7.1 WebUI).
- All quant-research deps (numpy, pandas, etc.) — untouched.

### 5.2 npm dependencies (`webui/package.json`)

**New (v0.7.2):**

- `html2canvas` (≥ 1.4) — already in v0.7.1's `dependencies`
  for the v0.7.1 Export HTML path. v0.7.2 reuses it for the
  in-view screenshot (Story 10). No new install needed; if
  v0.7.1's `html2canvas` was deferred, v0.7.2 adds it now.

**Unchanged from v0.7.1:**

- `react`, `react-dom` (18.x)
- `react-router-dom` (6.x)
- `framer-motion` (11.x)
- `chart.js` (4.x)
- `tailwindcss`, `autoprefixer`, `postcss`
- `vite`, `typescript`
- All test deps (`vitest`, `@testing-library/react`,
  `@playwright/test`, `msw`, `openapi-typescript`).

**Explicitly NOT added in v0.7.2:**

- No new charting library (Chart.js still covers 100 % of needs).
- No new animation library (Framer Motion still covers 100 %).
- No `lodash` / `ramda` (use stdlib + 5-line helpers).
- No `axios` (use `fetch` wrapper already in `webui/src/api/client.ts`).
- No CSS-in-JS (`styled-components`, `emotion`) — Tailwind only.

### 5.3 GitHub Actions workflows

**New (v0.7.2):**

- `.github/workflows/docs.yml` — runs on push to `main`, builds
  the MkDocs site, deploys to GitHub Pages. Triggered ONLY on
  changes to `docs-site/**` or `.github/workflows/docs.yml`
  (`paths:` filter). Failure of this workflow does NOT block
  PR merge (separate job).

**Unchanged from v0.7.1:**

- `.github/workflows/test.yml` — Python tests on push + PR.
- `.github/workflows/webui.yml` — Vite build + Vitest + Playwright.
- `.github/workflows/release.yml` — tagged-release automation.

### 5.4 External services

**None added in v0.7.2.**

- No CDN (Chart.js, Framer Motion, html2canvas all bundled via
  npm / Vite — same as v0.7.1).
- No auth service (no third-party login; local dev only).
- No analytics service (Stretch Goal 5 is a single local
  counter, not an external service).
- No LLM API changes (v0.7.1 already uses OpenRouter via env var).
- No broker changes (Alpaca paper-by-default unchanged from v1.0).

### 5.5 Browser support matrix

| Browser       | Version  | Status        |
|---------------|----------|---------------|
| Chrome        | ≥ 110    | Full support  |
| Firefox       | ≥ 110    | Full support  |
| Safari        | ≥ 16     | Full support  |
| Edge          | ≥ 110    | Full support  |
| Mobile Safari | ≥ 16     | Best-effort (v0.7.2 is desktop-first) |
| Mobile Chrome | ≥ 110    | Best-effort (v0.7.2 is desktop-first) |

New in v0.7.2:

- `navigator.clipboard.writeText` requires a secure context
  (HTTPS or `localhost`). Since v0.7.2 share links are served
  from `127.0.0.1`, the secure-context requirement is met.
- `prefers-color-scheme: light` detection — all 4 browsers ≥
  listed versions support this.

### 5.6 Compatibility matrix with v0.7.1

| What                                    | v0.7.1 (shipped) | v0.7.2 (target)   |
|-----------------------------------------|------------------|-------------------|
| CLI subcommands                          | 5 (`backtest`, `optimize`, `fetch`, `report`, `loop`) | 5 (no new subcommands; `loop` gains `--no-launch` flag) |
| Loop artifacts shape (`runs/<rid>/`)     | `manifest.yaml` + `results.parquet` + `top5.json` + `report.md` + `progress.json` | identical (no new files; optional `.webui-port` + `.share.json`) |
| FastAPI endpoints                        | 7 JSON + `/healthz` + SSE | 7 JSON + `/healthz` + SSE + 3 new (`POST /api/runs/<rid>/share`, `GET /api/share/<token>`, `POST /api/runs/<rid>/replay`) |
| WebUI views                              | 4                | 4 (no new view; new route `/s/<token>` is a thin read-only wrapper around TopFive) |
| WebUI animations                         | 8 Framer Motion  | 8 (no new animations) |
| Python tests                             | ≥ 285            | ≥ 297 |
| TypeScript tests                         | ≥ 30             | ≥ 39 |
| E2E tests                                | ≥ 6              | ≥ 9 |
| `runs/<rid>/` back-compat with v0.7.0    | yes (no breaking) | yes (no breaking) |

---

## 6. Open Questions (need user confirmation before implementation)

These are NOT blockers for the requirements phase but they will
block implementation. The Coder dev agent should surface them
before writing code.

1. **Default share-link base URL.** Story 4 says
   `ALPHALOOP_SHARE_BASE_URL` defaults to
   `http://127.0.0.1:<port>`. Is the placeholder
   `alphaloop.example` acceptable, or should it be the project's
   PyPI / GitHub URL (e.g. `https://github.com/AlphaStrategyAI/alphaloop/blob/<rid>`)?

2. **Share-link storage location.** Per-run `runs/<rid>/.share.json`
   vs cross-run `~/.alphaloop/shares.json`. The PRD picks
   per-run; confirm or override.

3. **Password-protected share links.** Story 7 lists this as
   deferred. Confirm it's deferred (vs added to v0.7.2 if the
   timeline allows).

4. **Auto-launch confirmation modal.** Story 9 says `r` triggers
   a confirmation modal. Some users prefer no-confirmation for
   speed. Confirm the modal is desired.

5. **Screenshot of which element?** Story 10 says the visible
   `<main>` element. Should the screenshot include the topbar
   (with run_id, view name) or exclude it (cleaner for slides)?

6. **MkDocs vs Sphinx.** Story 11 picks MkDocs + Material.
   alphaloop's existing `docs/` is hand-written Markdown with
   no generator. Confirm MkDocs is acceptable (vs adding
   `sphinx` which is more common in Python projects).

7. **Docs site URL.** `AlphaStrategyAI.github.io/alphaloop/` —
   does the org have Pages enabled? (The v0.7 design doc
   assumes yes; needs verification.)

8. **Test count target.** § 3.5 says ≥ 297 / ≥ 39 / ≥ 9. Is
   this the right split, or should we aim higher on any side?

9. **HTML2canvas license.** `html2canvas` is MIT. No action
   needed; flagging for completeness.

10. **Headless heuristic.** Story 2 uses `$DISPLAY` (Linux) and
    `$SSH_TTY` as the headless heuristic. Are these the right
    signals, or should we add `if sys.platform == "darwin": assume
    desktop` and only check `$DISPLAY` on Linux?

---

## 7. References

- v0.7.1 design (this PRD builds on):
  `docs/design/v071-webui.md` (2045 lines)
- v0.7 design (hybrid loop):
  `docs/design/v07-hybrid-loop.md` (883 lines)
- v0.6 design (LLM judge):
  `docs/design/v06-llm-judge.md` (762 lines)
- v0.7.1 export (share-link starting point):
  `src/alphaloop/webui/export.py` (174 lines)
- v0.7.1 FastAPI JSON backend:
  `src/alphaloop/webui/api.py` (126 lines)
- v0.7.1 TopFiveView (where Share button lives):
  `webui/src/views/TopFiveView.tsx` (131 lines)
- v0.7.1 CLI main (where `--no-launch` flag is added):
  `src/alphaloop/cli/main.py` (258 lines)
- ROADMAP:
  `ROADMAP.md` § v0.7.2 (E1)
- Loop state file:
  `~/.hermes/profiles/coder/.claude/loops/alphaloop-v072-requirements-doc.md`
- Python `webbrowser` docs:
  https://docs.python.org/3/library/webbrowser.html
- Python `subprocess` docs:
  https://docs.python.org/3/library/subprocess.html
- MkDocs Material:
  https://squidfunk.github.io/mkdocs-material/
- GitHub Pages:
  https://docs.github.com/en/pages
- html2canvas:
  https://html2canvas.hertzen.com/

---

## 8. Self-check (Loop Engineering, per `~/.hermes/profiles/coder/CLAUDE.md`)

- [x] **Goal:** 5-section PRD for v0.7.2 covering auto-launch, share
       link, polish, docs, with 12 user stories and 5 acceptance
       groups.
- [x] **Plan:** Read v0.7.1 design + CLI main + WebUI views + export
       module → write 5-section PRD → verify ≥ 300 lines + 5 sections
       + ≥ 10 user stories.
- [x] **Verify:** `wc -l ≥ 300`, `grep "## Goals|Requirements|Acceptance|Out
       of Scope|Dependencies" ≥ 5`, `grep -c "Story \d" ≥ 10` — all
       three checks documented in the loop's verify block.
- [x] **Stop rule:** Requirements phase ends when verify passes AND
       user explicit OK received (per loop state file §"stop_when").
- [x] **State:** This PRD + the loop state file's `state.last_*`
       fields will be updated by the Coder agent on completion.
- [x] **Hard wall:** No code, no tests, no commits, no broker
       connections — only this `.md` (and the loop state file).