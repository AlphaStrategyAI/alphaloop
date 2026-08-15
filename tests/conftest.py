"""
Shared pytest configuration and fixtures for alphaloop data-source tests.

Unit tests mock all external network calls.
Integration tests are gated by the `integration` marker and only run when
requested via `pytest -m integration` or the env var `OPENSTRATEGY_INTEGRATION=1`.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure `src/` is on sys.path so `import alphaloop` works without the
# caller having to set PYTHONPATH=src. This mirrors the pattern that
# individual test files already use (`sys.path.insert(0, ".../src")`),
# and lets eval_soul.sh and similar wrappers run pytest directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd
import pytest

from alphaloop.judge import RawCompletion


def _integration_enabled() -> bool:
    """Return True if integration tests should run."""
    return os.environ.get("OPENSTRATEGY_INTEGRATION", "0").lower() in ("1", "true", "yes")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: tests that hit real APIs/network")
    config.addinivalue_line("markers", "no_lookahead: factor look-ahead audit tests (v1.1.1)")


def pytest_runtest_setup(item):
    """Skip integration tests unless explicitly enabled."""
    if item.get_closest_marker("integration") and not _integration_enabled():
        pytest.skip("integration tests disabled (set OPENSTRATEGY_INTEGRATION=1)")


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Return a small OHLCV DataFrame with a DatetimeIndex."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=dates,
    )


@pytest.fixture
def sample_yahoo_history() -> pd.DataFrame:
    """Return a DataFrame that mimics yfinance Ticker.history() output."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Volume": [1000, 1100, 1200, 1300, 1400],
            "Dividends": [0.0, 0.0, 0.0, 0.0, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )


@pytest.fixture
def sample_akshare_response() -> pd.DataFrame:
    """Return a DataFrame that mimics akshare stock_zh_a_hist output."""
    return pd.DataFrame(
        {
            "日期": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "开盘": [100.0, 101.0, 102.0],
            "收盘": [104.0, 105.0, 106.0],
            "最高": [105.0, 106.0, 107.0],
            "最低": [99.0, 100.0, 101.0],
            "成交量": [1000, 1100, 1200],
            "成交额": [100000.0, 110000.0, 120000.0],
        }
    )


# ---------------------------------------------------------------------------
# v0.6: LLM judge fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_env(monkeypatch):
    """Strip all LLM_* env vars so tests can install their own values.

    Returns the monkeypatch fixture so callers can chain `.setenv(...)`.
    """
    for var in (
        "LLM_MODEL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_TIMEOUT_S",
        "LLM_JUDGE_CONFIG",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class FakeLLMClient:
    """Test double for `LLMClient` (design doc § 4.2).

    Records every call and returns scripted responses in order. Tests
    can inject responses (JSON or broken-text) and assert on what
    the diagnostic saw.
    """

    def __init__(
        self,
        responses: Optional[list[str]] = None,
        *,
        raise_on_call: Optional[BaseException] = None,
        delay_ms: int = 0,
        model_name: str = "fake-llm-v1",
    ):
        self.responses = list(responses or [])
        self.raise_on_call = raise_on_call
        self.delay_ms = delay_ms
        self.model_name = model_name
        self.calls: list[dict] = []
        self._idx = 0

    def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> "RawCompletion":
        self.calls.append(
            {
                "messages": list(messages),
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.raise_on_call is not None:
            raise self.raise_on_call
        if self._idx >= len(self.responses):
            raise AssertionError(
                f"FakeLLMClient exhausted: {self._idx} calls, "
                f"only {len(self.responses)} responses scripted"
            )
        content = self.responses[self._idx]
        self._idx += 1
        prompt_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
        completion_tokens = max(1, len(content) // 4)
        return RawCompletion(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.model_name,
            latency_ms=self.delay_ms,
        )


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    """Default fake client with one 'good' response pre-scripted."""
    return FakeLLMClient(
        responses=[
            (
                '{"readability": {"score": 8, "reasoning": "clear", "evidence": "x"}, '
                '"decision_quality": {"score": 8, "reasoning": "ok", "evidence": "y"}, '
                '"risk_disclosure": {"score": 8, "reasoning": "ok", "evidence": "z"}}'
            )
        ],
        model_name="fake-llm-v1",
    )


GOOD_JUDGE_RESPONSE = (
    '{"readability": {"score": 8, "reasoning": "clear", "evidence": "x"}, '
    '"decision_quality": {"score": 8, "reasoning": "ok", "evidence": "y"}, '
    '"risk_disclosure": {"score": 8, "reasoning": "ok", "evidence": "z"}}'
)
