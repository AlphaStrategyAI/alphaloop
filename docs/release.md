# Cutting an alphaloop desktop release

The desktop app version is the single value shared by:

- `apps/desktop/src-tauri/tauri.conf.json`
- `apps/desktop/src-tauri/Cargo.toml` and the `alphaloop-desktop` entry in `Cargo.lock`
- `apps/desktop/package.json` and `package-lock.json`

`scripts/check_app_version.py` fails when those declarations disagree. The Python package version in `pyproject.toml` is not part of that set; the desktop UI does not display it.

Builds are **unsigned** on purpose. The release workflow does not sign or notarize them.

## Cut a release

1. Bump the declarations above to the same `X.Y.Z` and merge that change to `main`. Do not push a tag from a pull request.
2. On `main`, at the commit you want to ship, push a tag that matches the version exactly:

   ```bash
   git checkout main
   git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   `vX.Y.Z` must equal the `version` in `tauri.conf.json` with a `v` prefix. Any other tag fails the release job before it creates a GitHub Release.

3. The `desktop-release` workflow runs on that tag. It builds the Linux `.deb`, the macOS arm64 `.dmg` and `.app.tar.gz`, and the Windows NSIS setup (and MSI). It checks the tag, writes `SHA256SUMS.txt`, and opens a **draft** GitHub Release marked **prerelease**. It does not publish the release.
4. Open the draft. Confirm the installers and `SHA256SUMS.txt` are attached. Replace the placeholder per-platform test section with the real results (Windows CI summary, plus the Linux and macOS checklist below).
5. Publish the draft only after those checks look right. Publishing is a separate, manual step.

`workflow_dispatch` on `desktop-release` builds the three installers and skips creating a release. Use that to rehearse the build. It still does not push a tag.

Installer names come from `tauri.conf.json`, not from a hardcoded version:

- `alphaloop_<version>_linux_amd64.deb`
- `alphaloop_<version>_macos_arm64.dmg`
- `alphaloop_<version>_macos_arm64.app.tar.gz`
- `alphaloop_<version>_windows_x64-setup.exe`
- `alphaloop_<version>_windows_x64.msi`

Linux packages are built on `ubuntu-22.04` so the `.deb` links against that glibc. macOS packages are arm64 (Apple Silicon) from `macos-14`.

## Unsigned installs

- **macOS:** Right-click the app and choose Open, or after mounting the disk image run `xattr -dr com.apple.quarantine` on the `.app`.
- **Windows:** If SmartScreen appears, choose More info → Run anyway.
- **Linux:** install the `.deb` with your package manager. The package is not signed by a distribution key.

## Windows CI

Pull requests run `desktop-release-windows` / `windows-e2e`. That job installs the setup executable silently, drives the GUI with `tauri-driver` and `msedgedriver`, and uploads:

- `windows-e2e-screenshots`
- `windows-e2e-logs` (app `desktop.log`, engine `engine.log`, and the driver log)

The job summary lists each step as pass, fail, or skipped. A skip means an earlier step failed, or a step could not be automated; a skip is not a pass. The test process sets `ALPHALOOP_OFFLINE_MARKET_DATA=1` and `ALPHALOOP_SECRETS_BACKEND=passphrase`. Both default off in a normal launch, so the installed app still uses Yahoo/Sina and the OS keyring unless those variables are set.

## Manual checklist (Linux and macOS)

Repeat this on a clean user account. On Windows, prefer the CI job above; use this list only when you are checking a machine by hand.

1. Install the package. Launch alphaloop. The engine sidecar starts and the window shows no traceback and no error banner.
2. Switch the interface language Chinese → English, then English → Chinese, and back to English. On the English UI, the rail, secrets panel, confirm card, and conclusion page chrome contain no CJK characters. Text you typed yourself can still be Chinese.
3. Open the secrets panel with no passphrase file. It is not locked. Create a passphrase, quit, launch again, and unlock.
4. Start a research from natural language for one US stock and one A-share (`600519`). Each reaches its own confirm card. With several confirm cards on the list, opening one opens that research and not the other.
5. Confirm a run and let it finish. The conclusion page renders. Export writes a file.
6. Delete a research while it is running. The engine process stays up.
7. Quit and launch again. The research you kept is still there. The one you deleted is not.
8. Uninstall silently (or with the platform uninstaller) and confirm the app is gone.

Market data in CI is synthetic. A manual pass on Linux or macOS can use the same `ALPHALOOP_OFFLINE_MARKET_DATA=1` switch when you do not want the machine to call Yahoo or Sina.
