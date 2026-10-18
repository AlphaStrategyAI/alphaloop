# Tech Pulse UI (desktop)

Visual layer aligned with 设计小迪 Figma **Tech Pulse v003** (`night.css` + `tech-pulse.css`).

## Tokens

| Token | Value | Use |
|-------|-------|-----|
| void | `#07090C` | App background |
| ink | `#E8EEF5` | Primary text |
| cyan | `#5EEAD4` | Confirm / export accents |
| pulse | `#60A5FA` | Running orbit, quota meter |
| line | `#1E2530` | Borders |

## Motion

- UI transitions: `0.32s ease-out` (`--motion-fast`)
- Orbit “breathing”: `3.6s` (`--orbit-breathe`), disabled when `prefers-reduced-motion: reduce`
- Hover: border/glow only (no scale on press)
- **Run-start ritual** (~500ms): when view transitions `confirm_run` → `running`, applies `.run-start-ritual` on the shell (atmosphere fade-in) and `.run-start-ritual-running` on the running panel (orbit entrance). Skipped entirely when `prefers-reduced-motion: reduce`. No fake progress or invented metrics.

## Brand

Sidebar uses `src/assets/brand-icon-{96,192}.png` (from v2 transparent master). Tauri bundle icons under `src-tauri/icons/` are unchanged.

## Regenerate web brand assets

From repo root, resize the transparent master with Pillow or replace PNGs manually after design delivery.
