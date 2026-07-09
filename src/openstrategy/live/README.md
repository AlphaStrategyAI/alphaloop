# `openstrategy.live` — broker connectivity

Default: paper trading (sandbox).
Live trading: requires both `paper=False` AND `confirm_live=True`.

## Hard wall

This package cannot accidentally connect to a real-money brokerage
account. Construction of an `AlpacaAdapter` follows these rules:

1. **Default is paper.** `AlpacaAdapter()` connects to the sandbox.
2. **Live requires double opt-in.** Both `paper=False` and
   `confirm_live=True` must be set. Missing either raises
   `LiveTradingRefused` immediately at construction time.
3. **No silent fall-through.** There is no "warn and proceed" mode.
4. **The flag is verbose on purpose.** The string
   `confirm_yes_i_know_what_im_doing` is hard to mistype.

## Quick start

```python
from openstrategy.live import AlpacaAdapter, LiveTradingRefused

# Paper trading (default, no opt-in required)
broker = AlpacaAdapter(api_key="PK...", secret="...")
print(broker.is_paper)  # True
print(broker.base_url)  # https://paper-api.alpaca.markets

# Live trading requires explicit confirmation
broker = AlpacaAdapter(
    api_key="AK...",
    secret="...",
    paper=False,
    confirm_live=True,  # REQUIRED
)
print(broker.is_paper)  # False
print(broker.base_url)  # https://api.alpaca.markets

# Trying to go live without confirmation:
try:
    broker = AlpacaAdapter(
        api_key="AK...",
        secret="...",
        paper=False,
        # confirm_live missing!
    )
except LiveTradingRefused as e:
    print(f"refused: {e}")
```

## v1.0 scope

This subpackage provides read-only broker access for v1.0:

| Method | Description |
|--------|-------------|
| `get_account()` | Account summary (equity, cash, status) |
| `is_market_open()` | Market hours from broker clock |

The following are explicitly **out of v1.0 scope**:

- Order placement (`place_order`, `cancel_order`)
- Position listing
- Streaming / websockets

These will land in v2.0.

## Why the hard wall?

The v1.0 goal is "honest verifiable quantitative research
infrastructure." Per the Hermes project rules (and common sense):

> Quantitative projects are read-only by default. Any code that
> could route a request to a live brokerage account must be
> gated by an explicit, hard-to-mistype confirmation.

The two-flag pattern (`paper=False` + `confirm_live=True`) is
intentionally verbose. If you accidentally type
`AlpacaAdapter(paper=True)`, you cannot lose money. If you
deliberately type `AlpacaAdapter(paper=False, confirm_live=True)`,
you've made a decision that deserves the friction.

## Tests

```bash
cd /Users/assistant/hermes-lab/openstrategy
python3 -m pytest tests/live/ -v
```

All HTTP calls in tests are mocked via `monkeypatch` on
`urllib.request.urlopen`. **No test makes a real network request.**

## Adding a new broker

To add a new broker (IB, Futu, TD, etc.):

1. Implement the `Broker` protocol (see `broker.py`).
2. In your adapter's `__init__`, call `_enforce_safety(config)`.
3. Add tests that verify both safety interception AND mocked
   request behavior.
4. Never bypass `_enforce_safety`.