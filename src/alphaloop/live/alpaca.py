"""
Alpaca broker adapter.

Default: paper trading (sandbox at https://paper-api.alpaca.markets).
Live trading: requires both `paper=False` AND `confirm_live=True`.

This module does NOT initiate any HTTP connection at import time.
The actual REST calls live in private methods that are only invoked
when the user explicitly calls `get_account()` or `is_market_open()`.

v1.0 scope:
  - Construct the adapter with the correct base_url + safety check.
  - Surface a thin API: `is_paper`, `name`, `get_account`,
    `is_market_open`.
  - No order placement, no cancellation, no streaming.

For v2.0 (out of scope):
  - place_order, cancel_order, list_positions
  - websocket streaming for fills

References:
  - Alpaca paper trading base URL: https://paper-api.alpaca.markets
  - Alpaca live trading base URL:  https://api.alpaca.markets
  - Alpaca API docs:               https://alpaca.markets/docs/api-references/trading-api/
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .broker import BrokerConfig, _enforce_safety


PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"


class AlpacaAdapter:
    """Alpaca Markets adapter (paper by default).

    Construction is safe: this class makes no HTTP calls until you
    invoke a request method. Even then, the request method uses
    urllib.request directly (no third-party SDK required) so the
    dependency surface stays minimal.

    Example:
        >>> broker = AlpacaAdapter(api_key="PK...", secret="...")
        >>> broker.is_paper
        True
        >>> broker.get_account()  # paper sandbox request
        {'equity': 100000.0, 'cash': 100000.0, 'status': 'ACTIVE'}
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        paper: bool = True,
        confirm_live: "Optional[bool]" = False,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        # Normalize None to False so callers passing confirm_live=None
        # don't accidentally bypass the safety check.
        if confirm_live is None:
            confirm_live = False
        config = BrokerConfig(
            paper=paper,
            confirm_live=confirm_live,
            api_key=api_key,
            secret=secret,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        # Safety: live mode without explicit confirmation -> raise.
        _enforce_safety(config)

        self._config = config
        self._base_url = base_url or (PAPER_BASE_URL if paper else LIVE_BASE_URL)

    # --- Properties ---

    @property
    def is_paper(self) -> bool:
        return self._config.paper

    @property
    def name(self) -> str:
        return "alpaca"

    @property
    def base_url(self) -> str:
        return self._base_url

    # --- Read-only API (safe to call) ---

    def get_account(self) -> dict:
        """Fetch account summary from Alpaca.

        Returns a dict with at least: equity, cash, status.

        Raises:
            RuntimeError: if `api_key` or `secret` is missing.
            urllib.error.URLError: on network failure.
        """
        return self._request("GET", "/v2/account")

    def is_market_open(self) -> bool:
        """Return True if the Alpaca clock says the market is currently open."""
        data = self._request("GET", "/v2/clock")
        return bool(data.get("is_open", False))

    # --- Internals ---

    def _request(self, method: str, path: str) -> dict:
        """Make an authenticated request to Alpaca.

        Uses urllib.request so we don't need an SDK dep. Caller is
        expected to handle the exception. We deliberately do NOT
        catch and re-raise as something fancier — the underlying
        HTTPError is informative enough.
        """
        if not self._config.api_key or not self._config.secret:
            raise RuntimeError(
                "AlpacaAdapter requires api_key and secret to be set. "
                "Construct with AlpacaAdapter(api_key=..., secret=...)."
            )

        import urllib.request  # local import: keep top of file dep-free

        url = self._base_url.rstrip("/") + path
        req = urllib.request.Request(url, method=method)
        req.add_header("APCA-API-KEY-ID", self._config.api_key)
        req.add_header("APCA-API-SECRET-KEY", self._config.secret)
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=self._config.timeout_seconds) as resp:
            payload = resp.read().decode("utf-8")
        return json.loads(payload)

    def __repr__(self) -> str:
        mode = "paper" if self.is_paper else "LIVE"
        return f"<AlpacaAdapter mode={mode} base_url={self._base_url!r}>"