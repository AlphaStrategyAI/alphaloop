"""
Tests for the v0.7.2 R-AutoLaunch feature.

Covers:
* pick_free_port + port fallback (5173 → 5174 → ... → 5183 → ephemeral)
* is_headless heuristic
* write_port_artifact
* --no-launch flag on the CLI subcommand
* auto_launch orchestrator (no_launch / mocked spawn / mocked browser)
"""
from __future__ import annotations

import argparse
import importlib
import socket
import sys
from pathlib import Path
from unittest import mock

import pytest

from alphaloop.webui import auto_launch as al

# Import the *module* (not the main() function). The cli package's
# __init__.py re-exports `main` as the function, which would shadow the
# submodule on `from alphaloop.cli import main`. Use importlib to bypass.
cli_main = importlib.import_module("alphaloop.cli.main")


# ---------------------------------------------------------------------
# Port picking
# ---------------------------------------------------------------------


def test_pick_free_port_finds_first_available():
    """pick_free_port returns the start port when free."""
    port = al.pick_free_port(host="127.0.0.1", start=5230, end=5240)
    assert port == 5230


def test_pick_free_port_fallback_when_occupied():
    """If start is busy, pick_free_port walks up the range."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", 5241))
        s.listen(1)
        port = al.pick_free_port(host="127.0.0.1", start=5241, end=5243)
        assert port == 5242
    finally:
        s.close()


def test_pick_free_port_ephemeral_fallback():
    """If the whole range is occupied, fall back to an OS-assigned port."""
    socks = []
    try:
        for p in range(5255, 5261):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", p))
            s.listen(1)
            socks.append(s)
        port = al.pick_free_port(host="127.0.0.1", start=5255, end=5260)
        # Ephemeral port is NOT in our occupied range.
        assert port > 5260 or port < 5255
    finally:
        for s in socks:
            s.close()


# ---------------------------------------------------------------------
# Headless heuristic
# ---------------------------------------------------------------------


def test_is_headless_false_on_macos(monkeypatch):
    import platform

    if platform.system() == "Darwin":
        assert al.is_headless() is False
    else:
        # On Linux without DISPLAY, should be True.
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert al.is_headless() is True


def test_is_headless_linux_with_display(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    assert al.is_headless() is False


def test_is_headless_linux_without_display(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert al.is_headless() is True


# ---------------------------------------------------------------------
# Port artifact
# ---------------------------------------------------------------------


def test_write_port_artifact(tmp_path: Path):
    p = al.write_port_artifact(tmp_path, 5176)
    assert p.exists()
    assert p.name == ".webui-port"
    assert p.read_text() == "5176\n"


# ---------------------------------------------------------------------
# CLI --no-launch flag
# ---------------------------------------------------------------------


def test_cli_loop_no_launch_flag_accepted():
    """`alphaloop loop run --no-launch` parses without error."""
    parser = cli_main.create_parser()
    args = parser.parse_args(["loop", "run", "demo", "--no-launch"])
    assert args.no_launch is True
    assert args.loop_command == "run"


def test_cli_loop_default_no_launch_false():
    parser = cli_main.create_parser()
    args = parser.parse_args(["loop", "run", "demo"])
    assert args.no_launch is False


def test_cli_loop_short_form_no_launch():
    """Short form `alphaloop loop <goal> --no-launch` parses too."""
    parser = cli_main.create_parser()
    args = parser.parse_args(["loop", "demo", "--no-launch"])
    assert args.no_launch is True


# ---------------------------------------------------------------------
# auto_launch orchestrator (no actual subprocess / browser)
# ---------------------------------------------------------------------


def test_auto_launch_no_launch_returns_empty():
    """no_launch=True short-circuits the orchestrator."""
    ok, url, port = al.auto_launch(
        run_id="r1", artifacts_dir="/tmp", no_launch=True
    )
    assert ok is False
    assert url is None
    assert port is None


def test_auto_launch_runs_with_mocked_spawn(monkeypatch, tmp_path):
    """When spawn is mocked, auto_launch returns (True, url, port) cleanly."""
    # The mocked server returns True on healthz by hitting the http
    # layer; we use a port we know is free and let uvicorn patch fail
    # silently — auto_launch should still return a port.
    monkeypatch.setattr(
        al, "spawn_webui_server", mock.MagicMock(return_value=mock.MagicMock())
    )
    monkeypatch.setattr(al, "_wait_for_http", lambda url, timeout_s=15.0: True)
    monkeypatch.setattr(al, "open_in_browser", lambda url: True)
    monkeypatch.setattr(al, "is_headless", lambda: False)

    ok, url, port = al.auto_launch(
        run_id="test-run-001",
        artifacts_dir=str(tmp_path),
        port_start=5270,
        port_end=5280,
    )
    assert ok is True
    assert url is not None
    assert "test-run-001" in url
    assert port == 5270
    assert (tmp_path / ".webui-port").exists()
    assert (tmp_path / ".webui-port").read_text() == "5270\n"


def test_auto_launch_swallows_browser_error(monkeypatch, tmp_path):
    """webbrowser.open failing must not crash the loop."""
    monkeypatch.setattr(
        al, "spawn_webui_server", mock.MagicMock(return_value=mock.MagicMock())
    )
    monkeypatch.setattr(al, "_wait_for_http", lambda url, timeout_s=15.0: True)
    monkeypatch.setattr(al, "is_headless", lambda: False)

    def _boom(url):
        raise RuntimeError("no browser")

    monkeypatch.setattr(al, "open_in_browser", _boom)

    ok, url, port = al.auto_launch(
        run_id="r2",
        artifacts_dir=str(tmp_path),
        port_start=5281,
        port_end=5282,
    )
    # ok is True even if browser failed — the server is up.
    assert ok is True
    assert url is not None
