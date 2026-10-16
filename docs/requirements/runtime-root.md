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

Cross-language parity: `tests/test_runtime_root_contract.py` and `engine_paths` unit tests share the same fixture table.
