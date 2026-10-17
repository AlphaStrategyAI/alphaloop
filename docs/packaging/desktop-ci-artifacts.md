# Desktop CI installable artifacts

Unsigned desktop bundles are produced on push / `workflow_dispatch` for the `cursor/**` and `main` branches.

## Workflows

| Workflow | Runner | Artifact upload name |
|----------|--------|----------------------|
| `desktop-release-windows.yml` | `windows-latest` | `alphaloop-desktop-windows-<full-sha>` |
| `desktop-release-macos.yml` | `macos-latest` | `alphaloop-desktop-macos-<full-sha>` |

Download from the GitHub Actions run page: **Summary → Artifacts**, or `gh run download <run-id> -n <artifact-name>`.

## Windows artifact contents

After a successful run, the artifact folder `windows-<short-sha>/` contains:

- `*.msi` from `apps/desktop/src-tauri/target/release/bundle/msi/`
- NSIS `*.exe` from `apps/desktop/src-tauri/target/release/bundle/nsis/`

## macOS artifact contents

Folder `macos-<short-sha>/`:

- `alphaloop-macos-<short-sha>.zip` — zipped `.app` from `bundle/macos/`
- `alphaloop-macos-<short-sha>.dmg` — Tauri DMG when present, otherwise `hdiutil` fallback

## Local parity

1. `bash scripts/build_sidecar.sh`
2. `TARGET=macos|linux|windows bash scripts/stage_engine_for_tauri.sh`
3. `cd apps/desktop && npm ci && npm run tauri -- build`
