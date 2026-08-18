# AGENTS.md

## Cursor Cloud specific instructions

alphaloop is a Python quant-research framework (CLI + library) plus a web experience
made of a **FastAPI JSON backend** and a **Vite + React SPA**. There is no database;
persistence is filesystem-based under `runs/`.

The update script (run automatically on VM startup) creates a venv at `.venv/`,
installs the package's declared deps via `pip install -e ".[dev]"`, installs the
Node deps in `webui/`, and installs a few runtime deps that the project imports but
does **not** declare in `pyproject.toml` (`fastapi`, `uvicorn`, `httpx`, `pyarrow`).
Activate the environment with `. .venv/bin/activate` before running anything.

### Non-obvious gotchas

- **The package is NOT importable after `pip install -e .`.** `pyproject.toml` still
  declares the old package name `openstrategy` (`packages = ["src/openstrategy"]` and
  the `openstrategy` console script), but the real package lives at `src/alphaloop`.
  The editable install therefore resolves dependencies correctly but maps **no**
  package onto the path, and neither the `openstrategy` nor `alphaloop` console script
  works. Run everything with `PYTHONPATH=src` and the module form, e.g.:
  - CLI: `PYTHONPATH=src python -m alphaloop.cli.main report`
  - Loop (generates `runs/` artifacts, offline/synthetic by default):
    `PYTHONPATH=src python -m alphaloop.cli.main loop run "find alpha with DSR > 1.0" --seed 42 --no-launch`
  - Tests: `PYTHONPATH=src python -m pytest tests/ -q`
- **Backend needs `runs/` artifacts.** The FastAPI API only serves data that exists
  under `./runs/`; with no runs it returns empty lists / 404. Generate at least one
  run (see the loop command above) before exercising the WebUI end to end.
- **The `loop run` command prints `asyncio.queues.QueueFull` tracebacks.** These are
  non-fatal SSE-queue warnings; the run still completes and writes artifacts.

### Services

- **FastAPI backend** — port 8000. Run:
  `PYTHONPATH=src uvicorn alphaloop.webui.api:app --host 0.0.0.0 --port 8000`
  (`runs_dir` defaults to `./runs`; `/healthz` reports run count).
- **Vite React SPA** — port 5173 (`strictPort: true`, so the port must be free).
  Run `npm run dev` in `webui/`. It proxies `/api` → `http://localhost:8000`, so the
  backend must be running for data to load.
- **Streamlit UI** (`src/alphaloop/ui.py`) and the MkDocs docs-site are optional and
  not required for the core flows. Streamlit is not installed by the update script.

### Lint / test / build (see `pyproject.toml` and `webui/package.json` for the source of truth)

- Python tests: `PYTHONPATH=src python -m pytest tests/ -q`. Known pre-existing
  failure: `tests/test_loop.py::test_cli_loop_subcommand_help` hardcodes the original
  author's absolute path (`/Users/assistant/hermes-lab/alphaloop`) and always fails in
  any other environment — not an environment problem.
- Python lint: `ruff check src tests` and `black --check src tests` (both installed by
  the `dev` extra).
- Frontend lint / build: `npm run lint` (`tsc --noEmit`) and `npm run build` in `webui/`.
- Frontend unit tests: `npm run test` (Vitest). Vitest currently also collects the
  Playwright spec `webui/e2e/webui.spec.ts`, which fails on `import "@playwright/test"`
  because Playwright is not installed; the 26 real unit tests still pass. The Playwright
  e2e suite (`npm run test:e2e`) needs `@playwright/test` + `npx playwright install`.
