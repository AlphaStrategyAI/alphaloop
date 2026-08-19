from dataclasses import dataclass


@dataclass(frozen=True)
class MarketProfile:
    name: str
    periods_per_year: int
    default_benchmark: str
    cost_bps: float
    calendar: str


US_EQUITY_DAILY = MarketProfile(
    name="us-equity-daily",
    periods_per_year=252,
    default_benchmark="SPY",
    cost_bps=5.0,
    calendar="nyse",
)
