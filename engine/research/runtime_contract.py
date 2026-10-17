"""Injectable runtime-root resolver for cross-language contract tests (`tests/fixtures/runtime_root_cases.json`)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

GetEnv = Callable[[str], str | None]
RuntimeDirUsable = Callable[[Path, int], bool]


def resolve_runtime_root_contract(
    *,
    uid: int,
    temp_dir: Path,
    getenv: GetEnv | None = None,
    runtime_dir_usable: RuntimeDirUsable | None = None,
) -> Path:
    """Same precedence as `docs/requirements/runtime-root.md` / Rust `engine_paths`."""
    env_get = getenv or os.environ.get
    usable = runtime_dir_usable or _production_runtime_dir_usable

    override = env_get("ALPHALOOP_RUNTIME_ROOT")
    if override:
        return Path(override)

    if xdg := env_get("XDG_RUNTIME_DIR"):
        xdg_path = Path(xdg)
        if usable(xdg_path, uid):
            return xdg_path / "alphaloop"

    run_user = Path(f"/run/user/{uid}")
    if usable(run_user, uid):
        return run_user / "alphaloop"

    fallback = temp_dir / f"runtime-{uid}"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "alphaloop"


def _production_runtime_dir_usable(path: Path, uid: int) -> bool:
    try:
        meta = path.lstat()
    except OSError:
        return False
    import stat

    if stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode):
        return False
    mode = meta.st_mode & 0o777
    return meta.st_uid == uid and mode == 0o700
