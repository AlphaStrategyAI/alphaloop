# Engine path contract — runtime vs data

Desktop (Rust) and engine (Python) must agree where **ephemeral runtime state** vs **persistent user data** live.

## Classification

| Path / artifact | Kind | Location |
| --- | --- | --- |
| `owner.json` | **Runtime** | `<runtime_root>/owner.json` |
| `engine.lock` | **Runtime** | `<runtime_root>/engine.lock` |
| `research.db` | **Data** | `<data_root>/research.db` |
| `materials/` | **Data** | `<data_root>/materials/` |
| `exports/` | **Data** | `<data_root>/exports/` |
| `snapshots/` | **Data** | `<data_root>/snapshots/` (CSV data snapshots) |
| `engine.log` | **Data** | `<data_root>/engine.log` |
| `settings.json` | **Data** | `<data_root>/settings.json` | App preferences. I0 owns `uiLanguage` (`system`, `zh`, or `en`). Not the research library and not the keychain. Writers must keep keys they do not own. Missing file or unknown `uiLanguage` reads as `system`. |
| Export zip `history/*.json` | **Data** (inside export artifact) | Generated at export time; not a separate on-disk tree |

Rust (`engine_paths`) touches **runtime only** (`owner.json`). The packaged engine resolves **data** paths on startup; the desktop does not pass a data directory over IPC.

## Overrides

| Variable | Purpose |
| --- | --- |
| `ALPHALOOP_RUNTIME_ROOT` | Runtime root (lock + owner); no `/alphaloop` suffix |
| `ALPHALOOP_DATA_ROOT` | Persistent data root |

Unset defaults match **platformdirs** with app id `ai.alphastrategy.alphaloop`:

- **Runtime:** `user_runtime_path("alphaloop")` — XDG → `/run/user/<uid>` → `<tempdir>/runtime-<uid>/alphaloop` (see `tests/fixtures/runtime_root_cases.json`).
- **Data:** `user_data_dir("ai.alphastrategy.alphaloop")` (e.g. Linux `~/.local/share/ai.alphastrategy.alphaloop`).

## Migration (pre-split layouts)

On `EnginePaths.default()`, if `<data_root>/research.db` is missing but `<runtime_root>/research.db` exists, copy the DB (verify size), optionally copy `materials/`, `exports/`, `snapshots/`, write `<data_root>/.migrated-from-runtime-root`, log, and **never delete** legacy files.

## Implementations

- Python: `engine.research.runtime` (`EnginePaths`, `RuntimePaths`, `DataPaths`), `path_migration.migrate_legacy_runtime_data`
- Rust: `engine_paths::resolve_runtime_root()` (runtime only)

Shared tests: `tests/fixtures/runtime_root_cases.json`, `tests/fixtures/data_root_cases.json`, `tests/test_runtime_root_contract.py`, `tests/test_data_root_contract.py`.
