from __future__ import annotations

import socket

import pytest

_REAL_SOCKET = socket.socket

from engine.research.pool_data_shrink import set_pool_data_loader
from tests.fixtures.pool_loader import AllSymbolsAvailableLoader


@pytest.fixture(autouse=True)
def _offline_pool_data_loader(request: pytest.FixtureRequest) -> None:
    """Default confirm-time pool checks offline unless a test replaces the loader."""
    if request.node.get_closest_marker("network"):
        yield
        return
    set_pool_data_loader(AllSymbolsAvailableLoader())
    yield
    set_pool_data_loader(None)


@pytest.fixture(autouse=True)
def _block_real_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("network"):
        return
    original_socket = socket.socket

    def guarded_socket(*args: object, **kwargs: object) -> socket.socket:
        family = args[0] if args else kwargs.get("family")
        if family == socket.AF_UNIX:
            return original_socket(*args, **kwargs)
        raise OSError("network blocked in offline tests (use @pytest.mark.network)")

    monkeypatch.setattr(socket, "socket", guarded_socket)


@pytest.fixture
def allow_loopback_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let a test bind 127.0.0.1 for loopback HTTP without opening outbound network."""
    monkeypatch.setattr(socket, "socket", _REAL_SOCKET)
