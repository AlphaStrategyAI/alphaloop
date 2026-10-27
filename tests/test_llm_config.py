"""Settings LLM endpoint: non-secret fields in settings.json, key in the vault id."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.research.llm_config import (
    BASE_URL_KEY,
    MODEL_KEY,
    PRIVACY_KEY,
    SECRET_ID,
    is_loopback_base_url,
    read_llm_settings,
    resolve_llm,
    write_llm_settings,
)
from engine.research.secret_memory import install_secrets, peek_secret


def test_settings_file_keeps_other_keys_and_never_stores_the_api_key(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"uiLanguage": "en", "dataSources": {"kept": True}, "llmApiKey": "sk-leak"}),
        encoding="utf-8",
    )
    saved = write_llm_settings(
        path,
        base_url="http://127.0.0.1:11434/v1",
        model="local-model",
        privacy_acknowledged=True,
    )
    assert saved.base_url == "http://127.0.0.1:11434/v1"
    assert saved.model == "local-model"
    assert saved.privacy_acknowledged is True
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["uiLanguage"] == "en"
    assert loaded["dataSources"] == {"kept": True}
    assert loaded[BASE_URL_KEY] == "http://127.0.0.1:11434/v1"
    assert loaded[MODEL_KEY] == "local-model"
    assert loaded[PRIVACY_KEY] is True
    assert "llmApiKey" not in loaded
    assert "sk-leak" not in path.read_text(encoding="utf-8")
    assert SECRET_ID == "llm-api-key"


def test_resolve_uses_the_vault_id_and_allows_an_empty_local_key(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    write_llm_settings(
        path,
        base_url="http://127.0.0.1:11434/v1",
        model="qwen",
        privacy_acknowledged=True,
    )
    local = resolve_llm(path, environ={})
    assert local is not None
    assert local.api_key == ""
    assert local.model == "qwen"
    install_secrets({SECRET_ID: "sk-from-vault"})
    try:
        remote_path = tmp_path / "remote.json"
        write_llm_settings(
            remote_path,
            base_url="https://api.openai.com/v1",
            model="gpt-4.1-mini",
            privacy_acknowledged=True,
        )
        remote = resolve_llm(remote_path, environ={})
        assert remote is not None
        assert remote.api_key == "sk-from-vault"
        assert peek_secret(SECRET_ID) == "sk-from-vault"
    finally:
        install_secrets({})


def test_remote_without_a_key_or_privacy_ack_stays_unconfigured(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    write_llm_settings(
        path,
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        privacy_acknowledged=False,
    )
    assert resolve_llm(path, environ={}) is None
    write_llm_settings(
        path,
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        privacy_acknowledged=True,
    )
    assert resolve_llm(path, environ={}) is None


def test_environment_still_overrides_the_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    write_llm_settings(
        path,
        base_url="http://127.0.0.1:11434/v1",
        model="file-model",
        privacy_acknowledged=False,
    )
    resolved = resolve_llm(
        path,
        environ={
            "ALPHALOOP_LLM_BASE_URL": "https://example.test/v1",
            "ALPHALOOP_LLM_MODEL": "env-model",
            "ALPHALOOP_LLM_API_KEY": "env-key",
        },
    )
    assert resolved is not None
    assert resolved.base_url == "https://example.test/v1"
    assert resolved.model == "env-model"
    assert resolved.api_key == "env-key"


def test_loopback_is_only_localhost_and_127(tmp_path: Path) -> None:
    assert is_loopback_base_url("http://127.0.0.1:11434/v1")
    assert is_loopback_base_url("http://localhost:11434/v1")
    assert is_loopback_base_url("http://[::1]:11434/v1")
    assert not is_loopback_base_url("http://192.168.1.8:11434/v1")
    assert not is_loopback_base_url("https://api.openai.com/v1")
    with pytest.raises(ValueError):
        write_llm_settings(
            tmp_path / "bad.json",
            base_url="https://user:sk-secret@example.com/v1",
            model="m",
            privacy_acknowledged=True,
        )


def test_read_ignores_a_key_left_in_an_old_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({BASE_URL_KEY: "http://localhost:1/v1", MODEL_KEY: "m", "llmApiKey": "sk"}),
        encoding="utf-8",
    )
    loaded = read_llm_settings(path)
    assert loaded.base_url == "http://localhost:1/v1"
    assert loaded.privacy_acknowledged is False
    blob = path.read_text(encoding="utf-8")
    assert "sk" in blob  # read does not rewrite; write is what strips it
