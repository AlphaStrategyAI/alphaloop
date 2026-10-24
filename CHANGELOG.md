# Changelog

All notable changes to alphaloop are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-10-23

### Added

- Desktop packages for Linux (Ubuntu 22.04 amd64 `.deb`), macOS Apple Silicon (`.dmg` and `.app` archive), and Windows x64 (NSIS setup).
- A tag workflow that opens a draft prerelease with `SHA256SUMS.txt` after the Windows installer test passes on that same build.
- Windows CI that installs the NSIS setup and drives the GUI, including the OS credential manager and the passphrase fallback.
- Version and git sha on the settings About card and on the first line of `engine.log`.
- A visible Test data badge when synthetic market data is turned on.

### Changed

- The desktop app and the Python package are version 0.9.0.
- macOS builds are ad-hoc signed and not notarized. Gatekeeper still warns.
- The sidecar's third-party Python packages, including PyInstaller, are installed from a hashed lockfile.

### Security

- Linux and Windows packages are unsigned. macOS uses an ad-hoc signature only, with no Apple notarization.
