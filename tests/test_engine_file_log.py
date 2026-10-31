"""Desktop engine serve writes the contracted engine.log."""

from __future__ import annotations

import logging
from pathlib import Path

from engine.main import configure_engine_file_log


def test_configure_engine_file_log_appends(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "engine.log"
    handler = configure_engine_file_log(path)
    try:
        logging.getLogger("alphaloop.engine").info("sidecar ready")
        handler.flush()
        text = path.read_text(encoding="utf-8")
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()
    assert "sidecar ready" in text
    assert "alphaloop 0.9.4" in text
