"""Settings acknowledgement survives a Windows rename denial."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.research.source_acknowledgement import acknowledged_at, record_acknowledgement

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def test_acknowledgement_persists(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"uiLanguage": "en"}\n', encoding="utf-8")
    stamp = record_acknowledgement("yahoo_daily", NOW, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["uiLanguage"] == "en"
    assert loaded["unlicensedAcknowledgements"]["yahoo_daily"] == stamp
    assert acknowledged_at("yahoo_daily", path) == stamp
    assert list(tmp_path.glob("*.tmp")) == []


def test_replace_retries_then_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.json"
    calls = {"n": 0}
    real = os.replace

    def flaky(source: str | Path, destination: str | Path) -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "Access is denied")
        real(source, destination)

    monkeypatch.setattr("engine.research.source_acknowledgement.os.replace", flaky)
    monkeypatch.setattr("engine.research.source_acknowledgement.time.sleep", lambda _seconds: None)
    stamp = record_acknowledgement("yahoo_daily", NOW, path)
    assert calls["n"] == 3
    assert acknowledged_at("yahoo_daily", path) == stamp
    assert list(tmp_path.glob("*.tmp")) == []


def test_locked_rename_still_writes_the_acknowledgement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"uiLanguage": "en"}\n', encoding="utf-8")

    def denied(source: str | Path, destination: str | Path) -> None:
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr("engine.research.source_acknowledgement.os.replace", denied)
    monkeypatch.setattr("engine.research.source_acknowledgement.time.sleep", lambda _seconds: None)
    stamp = record_acknowledgement("akshare_sina_daily", NOW, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["uiLanguage"] == "en"
    assert loaded["unlicensedAcknowledgements"]["akshare_sina_daily"] == stamp
    assert list(tmp_path.glob("*.tmp")) == []
