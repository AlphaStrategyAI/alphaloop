# Cutting an alphaloop desktop release

The desktop version is one value, checked by `scripts/check_app_version.py`:

- `apps/desktop/src-tauri/tauri.conf.json`
- `apps/desktop/src-tauri/Cargo.toml` and the `alphaloop-desktop` entry in `Cargo.lock`
- `apps/desktop/package.json` and `package-lock.json`
- `pyproject.toml`
- `apps/desktop/src/buildInfo.ts` and `engine/research/build_info.json`

`scripts/write_build_info.py` rewrites the last two from that version and from `ALPHALOOP_GIT_SHA`. `scripts/resolve_embedded_sha.py` chooses that sha. A tag build checks out the tag and embeds `git rev-parse HEAD^{commit}` (the tagged commit). If `github.sha` is an annotated tag object and that object is in the checkout, it is peeled and must match `HEAD`. A pull-request build embeds `GITHUB_SHA`, which is GitHub's merge commit for the pull request, so About on a PR installer is not the branch head. Packaged builds show the value on Settings → About and on the first line of `engine.log`. The release job refuses to open the draft unless the Linux, macOS, and Windows artifacts all embedded that same tagged commit.

## System requirements

- **macOS:** Apple Silicon only. The build is ad-hoc signed and not notarized.
- **Windows:** Windows 10 or Windows 11, x64, with the WebView2 runtime.
- **Linux:** Ubuntu 22.04 or newer (the `.deb` is built on `ubuntu-22.04`).

## Cut a release

1. Bump the declarations above together, update `CHANGELOG.md`, and merge to `main`. Do not push a tag from a pull request.
2. The tagged commit must already be on `origin/main`. From `main`:

   ```bash
   git checkout main
   git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   `vX.Y.Z` must equal the `version` in `tauri.conf.json` with a `v` prefix. The release job rejects any other tag, and it rejects a tag that is not an ancestor of `origin/main`.

3. `desktop-release` builds Linux, macOS, and Windows once. The Windows GUI test installs that same NSIS setup. The macOS GUI test unpacks that same `.app` archive. Only after both pass does the workflow open a **draft** GitHub Release marked **prerelease**, with the installers and `SHA256SUMS.txt`. It does not publish the release.
4. Download the DMG in a browser from the draft so macOS applies quarantine. 开发小牛 confirms checksums (`sha256sum -c SHA256SUMS.txt`), signing, codesign, and SmartScreen on the package-level REPORT before notifying Master Bot. That check is out of scope for 产品小马. Replace the placeholder test-results table with the real Windows CI result and the Linux and macOS checklist below.
5. Master Bot asks the user to publish only after 开发小牛 package-level PASS and 产品小马 **全量 PASS** on the product matrix below. Publishing is a separate manual step.

`workflow_dispatch` on `desktop-release` builds the installers, runs the Windows and macOS GUI tests, and does not create a release.

Installer names come from `tauri.conf.json`:

- `alphaloop_<version>_linux_amd64.deb`
- `alphaloop_<version>_macos_arm64.dmg`
- `alphaloop_<version>_macos_arm64.app.tar.gz`
- `alphaloop_<version>_windows_x64-setup.exe`

Linux: `sudo apt install ./alphaloop_<version>_linux_amd64.deb`

## Signing

macOS is ad-hoc signed (`APPLE_SIGNING_IDENTITY=-` and `bundle.macOS.signingIdentity` `-`) and not notarized. `codesign --verify --deep --strict` runs in CI on the `.app` and on the bundled engine. Gatekeeper still warns. On macOS 15 and later, right-click → Open does not bypass that warning.

1. Download the DMG in a browser from the draft release (quarantine is set only for a browser download).
2. Drag the app to Applications.
3. Open it once and let Gatekeeper block it.
4. System Settings → Privacy & Security → Open Anyway.

After the app is in Applications, the alternative is:

```bash
xattr -dr com.apple.quarantine /Applications/alphaloop.app
```

Do not run `xattr` on the copy inside the mounted DMG. That volume is read-only.

Windows is not Authenticode-signed. If SmartScreen appears, choose More info → Run anyway.

The Linux package is not signed by a distribution key.

## Desktop CI end-to-end

Pull requests, and the tag release run, execute `windows-e2e` against the NSIS setup from that same workflow. Screenshots are the artifact `windows-e2e-screenshots`. App and engine logs are `windows-e2e-logs`. The job summary lists each step. A skip is not a pass.

The same runs execute `macos-e2e` (job id `macos-e2e` in `desktop-release-macos.yml`) against `alphaloop_<version>_macos_arm64.app.tar.gz` from that same workflow. The runner is `macos-15` (arm64). `macos-14` is retired and is not a fallback. Screenshots are `macos-e2e-screenshots`. App and engine logs are `macos-e2e-logs`. The job summary lists each step. A skip is not a pass. Push to `main` or `cursor/**` builds the bundle and does not run either GUI job; `desktop-release.yml` passes `run_e2e: true` into both reusable workflows.

The macOS job unpacks the `.app` tar.gz rather than mounting the DMG. The DMG is a read-only wrap of that same bundle. CI clears `com.apple.quarantine` and execs `Contents/MacOS` directly. `open` is not used, because LaunchServices is what presents the unidentified-developer dialog for an ad-hoc, notarized-missing build. A Finder launch of a browser-downloaded DMG can still be blocked; that is a product limit, and it does not skip `macos-e2e`.

Official `tauri-driver` cannot drive WKWebView. `macos-e2e` sets `ALPHALOOP_WEBDRIVER=1` so the macOS build's embedded W3C server (`tauri-plugin-wdio-webdriver`) listens on `127.0.0.1`, and Selenium drives it. A normal launch does not set that variable, and the unpacked-app smoke checks that port 4445 stays closed. The plugin code is in the macOS artifact; the socket is not.

Both GUI jobs use synthetic prices (`ALPHALOOP_OFFLINE_MARKET_DATA=1`), `ALPHALOOP_MAX_TRIALS=1`, `ALPHALOOP_E2E_HOLD_RUNNING_SEC=45`, and `ALPHALOOP_REVIEWER=deterministic`. One step uses the platform keyring (Windows credential manager, or the macOS login keychain). A later step sets `ALPHALOOP_SECRETS_BACKEND=passphrase`, which defaults off. An ad-hoc signature can still raise a keychain ACL dialog. The job unlocks the login keychain and then requires the keyring step to pass.

## Product acceptance before publish

Before asking the owner to publish a draft (or to treat a prerelease as ready), the gate order is: tag/draft candidate package → **开发小牛 package-level PASS** (installers, sha/signing/codesign/SmartScreen on their REPORT, new-feature + main regression, self-test/self-fix, then notify Master Bot) → **产品小马** runs the full product matrix in [`docs/requirements/release-acceptance-v1.md`](./requirements/release-acceptance-v1.md) against the candidate installers → Master Bot asks the user to publish.

- That file is the single source of truth for product release acceptance (scenarios, priority, PASS rules). Package sha256, signing, codesign, and SmartScreen verification are 开发小牛's package-level gate and are out of scope for this matrix.
- CI (including `windows-e2e` and `macos-e2e`) is an entry condition; it does not replace the matrix.
- Master Bot asks the user to publish only after 开发小牛 package-level PASS and 产品小马 reports **全量 PASS**.
- When a change alters UI, copy, gates, or settings, 开发小牛 updates the matching rows in the same PR or a follow-up docs PR.
- Per-release evidence: `docs/reports/YYYY-MM-DD-release-vX.Y.Z-product.md` (draft runs may stay under a local smoke folder until filed).

The short “Manual checklist (Linux and macOS)” below remains a quick smoke aid; it does not supersede the matrix.

## Manual checklist (Linux and macOS)

1. Install the package. Launch alphaloop. The engine sidecar starts, and the window shows no traceback and no error banner. Settings → About shows the version and commit.
2. Switch the interface language Chinese → English → Chinese → English. On the English UI, the rail, secrets panel, confirm card, and conclusion page chrome contain no CJK characters. Text you typed can still be Chinese.
3. Open secrets with no passphrase file. It is not locked. Create a passphrase, quit, launch again, and unlock. On Windows, also confirm the credential manager path before forcing the passphrase file.
4. Start a research from natural language for one US stock and for A-share `600519`. Each reaches its own confirm card. Opening one card opens that research.
5. Confirm a run and let it finish. The conclusion page renders. Export writes a file.
6. Delete a research while it is running. The engine process stays up.
7. Quit and launch again. The research you kept is still there. The deleted one is not.
8. Uninstall and confirm the app is gone.

`ALPHALOOP_OFFLINE_MARKET_DATA=1` shows a Test data badge and keeps the run off Yahoo and Sina. Leave it unset for a real data check.

## Dialogue-driven research

Packages ship the dialogue-driven research switch **off**. The control is Settings → General → Dialogue-driven research (`dialogueDrivenResearchEnabled` in `settings.json`). While it is off, the original slot rules and the existing confirm, pause, reverify, and export buttons stay in use.

`ALPHALOOP_DIALOGUE_V2=1` enables the new dialogue path only when that settings key is absent. An explicit `false` in `settings.json` wins. A closed write gate (`dialogue-write-gate.json` next to `research.db`) stops new dialogue writes and keeps the command journal. Do not default the switch on until an internal package has passed the product matrix and a voluntary cohort has used it.

Before an upgrade, take the SQLite consistency backup and its linked snapshots (`create_upgrade_backup` in `engine/research/dialogue_rollout.py`) and restore them into a temporary data directory before trusting the copy. The holdout harness and its seal live in `docs/requirements/dialogue-holdout-v1.md`. That harness is not a scored 114/120 model result.

## Known limitations

- Windows and macOS GUI entry checks run in GitHub Actions (`windows-e2e`, `macos-e2e`). They use synthetic market data.
- macOS CI runs on `macos-15`. The build is ad-hoc signed and not notarized. Linux and Windows builds are unsigned. Gatekeeper can still block a Finder launch of a browser-downloaded DMG. The guest framebuffer stays about 1024×768 (no VMware Tools, so the display cannot be raised). When the confirm card will not fit that screen, the job scrolls the symbol list into view and screenshots that.
- The macOS artifact contains an embedded WebDriver server that listens only when `ALPHALOOP_WEBDRIVER=1`.
