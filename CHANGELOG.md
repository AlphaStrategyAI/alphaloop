# Changelog

All notable changes to alphaloop are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.1] - 2026-10-24

### Fixed

- M1: a thesis that names fundamentals, stock-bond, all-weather, or low-vol is classified explicitly. The card states that mean reversion is what will run. Papers are filtered by the detected family.
- M2: a momentum card that says the family is not supported keeps Run disabled and shows that this family cannot run yet.
- M3: stock-bond and all-weather theses are recognized in the dialogue and reach their card. `STRATEGY_FAMILY_NOT_RUNNABLE` is reachable from that dialogue.
- M4: the completed page shows annualized excess return and maximum drawdown in Chinese and English.
- M5: removing one market recomputes the price source from the stored per-source acknowledgement and clears a stale unlicensed-source error.
- M6: engine dialogue, the round-change line, the default title, method definitions, and glossary bodies are i18n keys. English for the new lines is draft except the default title.
- M7: a failed study's result chip says the methods did not all pass, instead of the check name.

### Changed

- The desktop app and the Python package are version 0.9.1. The 0.9.0 tag is unchanged.

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
