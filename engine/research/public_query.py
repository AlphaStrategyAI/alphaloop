"""Public material queries. The free-text thesis never becomes a URL or error line."""

from __future__ import annotations

# Phrases the engine may send to a public provider. Anything else stays local.
_PUBLIC_PHRASES: tuple[str, ...] = (
    "equity mean reversion",
    "mean reversion",
    "均值回归",
    "low volatility",
    "低波",
    "all weather",
    "全天候",
    "fundamental factor",
    "基本面因子",
    "stock bond rebalance",
    "股债再平衡",
    "reversal",
    "反转",
)

POLICY_REVISION = "public-query-v1"


def public_query_text(query: str) -> str:
    """Whitelist projection of ``query``. Empty when nothing is authorized to leave."""
    if not query:
        return ""
    lowered = query.lower()
    found = [phrase for phrase in _PUBLIC_PHRASES if phrase.lower() in lowered]
    found.sort(key=len, reverse=True)
    kept: list[str] = []
    for phrase in found:
        if any(phrase.lower() in earlier.lower() for earlier in kept):
            continue
        kept.append(phrase)
    return " ".join(kept)


def redact_provider_error(prefix: str, exc: BaseException, raw_query: str) -> str:
    """Provider failures stay diagnostic without the original thesis or path."""
    message = f"{prefix}: {type(exc).__name__}"
    if raw_query and raw_query in message:
        message = message.replace(raw_query, "[redacted]")
    projected = public_query_text(raw_query)
    if projected and projected != raw_query and raw_query:
        # The exception text is not included; this only strips a leak if one was added.
        message = message.replace(raw_query, "[redacted]")
    return message
