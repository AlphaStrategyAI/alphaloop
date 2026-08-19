from alphaloop.protocol.profiles.us_equity_daily import MarketProfile

CRYPTO_DAILY = MarketProfile(
    name="crypto-daily",
    periods_per_year=365,
    default_benchmark="BTC-USD",
    cost_bps=10.0,
    calendar="247",
)
