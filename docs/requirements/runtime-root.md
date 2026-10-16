# Engine runtime directory contract

Desktop (Rust) and engine (Python) must resolve the **same** runtime root so `owner.json`, `engine.lock`, and `research.db` align.

## Precedence

1. **`ALPHALOOP_RUNTIME_ROOT`** — if set, use this path as the runtime root (no extra suffix).
2. **Platform user runtime dir** — same rules as `platformdirs.user_runtime_path("alphaloop")` on Unix:
   - If `XDG_RUNTIME_DIR` is set and passes the XDG runtime-dir checks (owned directory, mode `0700`, not a symlink), use `$XDG_RUNTIME_DIR/alphaloop`.
   - Else if `/run/user/<uid>` exists and passes the same checks, use `/run/user/<uid>/alphaloop`.
   - Else use `<tempdir>/runtime-<uid>/alphaloop` (create `<tempdir>/runtime-<uid>` with mode `0700` when possible).

On non-Linux, use the same base directory as `platformdirs` for the app name `alphaloop` (typically via `dirs::runtime_dir()` + `/alphaloop`).

## Files

| Path | Purpose |
| --- | --- |
| `<root>/owner.json` | Desktop/engine ownership handshake |
| `<root>/engine.lock` | Exclusive engine lock |
| `<root>/research.db` | SQLite store |

## Implementations

- Python: `engine.research.runtime.resolve_runtime_root()`
- Rust: `engine_paths::resolve_runtime_root()`

Cross-language parity: shared fixture table `tests/fixtures/runtime_root_cases.json` — consumed by `tests/test_runtime_root_contract.py` (Python `runtime_contract.resolve_runtime_root_contract`) and Rust `engine_paths::tests::shared_fixture_table_runtime_root` with injectable `runtime_dir_usable` / env probes (host-independent).

Production Python uses `platformdirs.user_runtime_path("alphaloop")` (same precedence as above on Linux). Production Rust uses `engine_paths::resolve_runtime_root()` with filesystem probes matching platformdirs.
