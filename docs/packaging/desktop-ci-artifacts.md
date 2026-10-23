# Desktop CI installable artifacts

Unsigned desktop bundles are produced on push and pull request for `cursor/**` and `main`.

The file names use the version in `apps/desktop/src-tauri/tauri.conf.json`.

## Workflows

| Workflow | Runner | Artifact name |
|----------|--------|----------------|
| `desktop-release-linux.yml` | `ubuntu-22.04` | `alphaloop_<version>_linux_amd64.deb` |
| `desktop-release-macos.yml` | `macos-14` (arm64) | `alphaloop_<version>_macos_arm64.dmg` and `alphaloop_<version>_macos_arm64.app.tar.gz` |
| `desktop-release-windows.yml` | `windows-latest` | `alphaloop_<version>_windows_x64-setup.exe` and `alphaloop_<version>_windows_x64.msi` |

Pull requests also run the Windows GUI end-to-end job. Screenshots are `windows-e2e-screenshots`. App and engine logs are `windows-e2e-logs`.

Download from the GitHub Actions run page: **Summary → Artifacts**, or `gh run download <run-id> -n <artifact-name>`.

Tag pushes of `v*` run `desktop-release.yml`, which rebuilds the three platforms and opens a draft prerelease. See [release.md](../release.md). That workflow does not run on pull requests.

## Signing

Signing and notarization are off. macOS builds have no Apple signing identity. Windows builds have no Authenticode certificate.

## Local parity

1. `bash scripts/build_sidecar.sh`
2. `TARGET=macos|linux|windows bash scripts/stage_engine_for_tauri.sh`
3. `cd apps/desktop && npm ci && npm run tauri -- build`

Linux CI passes `--bundles deb`. macOS CI passes `--target aarch64-apple-darwin`.

## Engine HTTP (market-data stalls)

The loopback API uses `ThreadingHTTPServer` so a hung Yahoo/AkShare probe on
`confirm_run` or confirm `fetch_view` does not block other `POST /commands`
calls. Market `load_daily` calls run under a **25s** overall deadline
(`ALPHALOOP_MARKET_DATA_TIMEOUT_SEC`); timeouts map to `DATA_SOURCE_UNAVAILABLE`.

## A-share / CN path (Master Bot retest)

After pulling this branch: `bash scripts/build_sidecar.sh` (rebuilds PyInstaller onedir with
`libmini_racer` for Sina akshare endpoints), then stage and `npm run tauri -- build`.
Confirm path uses `cn_equity_large_cap_v1` when universe symbols are empty; dialogue accepts
`600519.SH` tickers; daily data prefers Sina (`stock_zh_a_daily` / `stock_zh_index_daily`).
