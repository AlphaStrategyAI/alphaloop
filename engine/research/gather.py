from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

import akshare as ak
import httpx
import pandas as pd
import yfinance as yf

from engine.research import market_data_timeouts as _market_data_timeouts
from engine.research.data_availability import transient_data_error
from engine.research.market_data_timeouts import cn_market_data_max_workers, run_with_deadline



@dataclass(frozen=True, slots=True)
class Material:
    material_id: str
    source: str
    title: str
    url: str
    text: str
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class DataProfile:
    symbols: tuple[str, ...]
    years: int
    missing_pct: float


class MaterialPort(Protocol):
    def fetch(self, query: str) -> tuple[Material, ...]:
        raise NotImplementedError


class DataPort(Protocol):
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(slots=True)
class PapersAdapter:
    client: httpx.Client
    now: Callable[[], datetime]

    def fetch(self, query: str) -> tuple[Material, ...]:
        response = self.client.get(
            "https://api.crossref.org/works",
            params={"query": query, "rows": 5, "select": "DOI,title,URL,abstract"},
            timeout=20.0,
        )
        response.raise_for_status()
        result = []
        for item in response.json()["message"]["items"]:
            title = " ".join(item.get("title", ["Untitled"]))
            result.append(
                Material(
                    material_id=f"doi:{item['DOI']}",
                    source="papers",
                    title=title,
                    url=item.get("URL", f"https://doi.org/{item['DOI']}"),
                    text=item.get("abstract", title),
                    fetched_at=self.now(),
                )
            )
        return tuple(result)


@dataclass(slots=True)
class SecEdgarAdapter:
    client: httpx.Client
    now: Callable[[], datetime]
    user_agent: str

    def fetch(self, query: str) -> tuple[Material, ...]:
        response = self.client.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": self.user_agent},
            timeout=20.0,
        )
        response.raise_for_status()
        matches = []
        for item in response.json().values():
            haystack = f"{item['ticker']} {item['title']}".lower()
            if query.lower() in haystack:
                cik = str(item["cik_str"]).zfill(10)
                matches.append(
                    Material(
                        material_id=f"sec:{cik}",
                        source="sec-edgar",
                        title=f"{item['ticker']} — {item['title']}",
                        url=f"https://data.sec.gov/submissions/CIK{cik}.json",
                        text=f"EDGAR issuer record for {item['title']}",
                        fetched_at=self.now(),
                    )
                )
        return tuple(matches[:5])


@dataclass(frozen=True, slots=True)
class LocalMaterialAdapter:
    root: Path
    now: Callable[[], datetime]

    def fetch(self, query: str) -> tuple[Material, ...]:
        words = {word.lower() for word in query.split() if word}
        result = []
        for path in sorted(self.root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not words or any(word in text.lower() for word in words):
                result.append(
                    Material(
                        material_id=f"local:{path.name}",
                        source="local",
                        title=path.stem,
                        url=path.resolve().as_uri(),
                        text=text,
                        fetched_at=self.now(),
                    )
                )
        return tuple(result)


class YahooDataAdapter:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        provider_symbols = ["^GSPC" if symbol == "SPX" else symbol for symbol in symbols]
        frame = yf.download(
            provider_symbols,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
            progress=False,
        )
        close = frame.get("Close", frame)
        if len(symbols) == 1:
            close = close.to_frame(name=symbols[0]) if isinstance(close, pd.Series) else close
            close.columns = [symbols[0]]
        else:
            close = close.rename(columns={"^GSPC": "SPX"})
        return close.rename_axis("date").sort_index()  # type: ignore[no-any-return]


def _sina_listing_code(symbol: str, provider_symbol: str) -> str:
    if symbol.endswith(".SH"):
        return f"sh{provider_symbol}"
    if symbol.endswith(".SZ"):
        return f"sz{provider_symbol}"
    if symbol.endswith(".BJ"):
        return f"bj{provider_symbol}"
    return f"sh{provider_symbol}"


def _cn_equity_close(provider_symbol: str, symbol: str, start: date, end: date) -> pd.Series:
    """A-share daily close: Sina (akshare) first, Eastmoney akshare fallback."""
    sina_code = _sina_listing_code(symbol, provider_symbol)
    try:
        raw = ak.stock_zh_a_daily(symbol=sina_code, adjust="qfq")
        series = pd.Series(
            raw["close"].to_numpy(),
            index=pd.to_datetime(raw["date"]),
            name=symbol,
        )
        return series.loc[start.isoformat() : end.isoformat()]
    except Exception:
        raw = ak.stock_zh_a_hist(
            symbol=provider_symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        series = pd.Series(
            raw["收盘"].to_numpy(),
            index=pd.to_datetime(raw["日期"]),
            name=symbol,
        )
        return series.loc[start.isoformat() : end.isoformat()]


def _cn_csi300_close(start: date, end: date) -> pd.Series:
    symbol = "000300.SH"
    try:
        raw = ak.stock_zh_index_daily(symbol="sh000300")
    except Exception:
        raw = ak.stock_zh_index_daily_em(symbol="sh000300")
    series = pd.Series(
        raw["close"].to_numpy(),
        index=pd.to_datetime(raw["date"]),
        name=symbol,
    )
    return series.loc[start.isoformat() : end.isoformat()]


def _slice_series_to_window(series: pd.Series, start: date, end: date) -> pd.Series:
    if series.empty:
        return series
    return series.loc[start.isoformat() : end.isoformat()]


def _fetch_cn_symbol_series(symbol: str, start: date, end: date) -> pd.Series:
    if symbol == "CBA00101.CS":
        raw = ak.bond_new_composite_index_cbond(indicator="财富", period="总值")
        series = pd.Series(
            raw["value"].to_numpy(),
            index=pd.to_datetime(raw["date"]),
            name=symbol,
        )
    elif symbol.startswith("CN_BOND:"):
        provider_symbol = symbol.removeprefix("CN_BOND:")
        raw = ak.bond_zh_hs_daily(symbol=provider_symbol)
        series = pd.Series(
            raw["close"].to_numpy(),
            index=pd.to_datetime(raw["date"]),
            name=symbol,
        )
    elif symbol.startswith("CN_FUND:"):
        provider_symbol = symbol.removeprefix("CN_FUND:")
        raw = ak.fund_etf_hist_em(
            symbol=provider_symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        series = pd.Series(
            raw["收盘"].to_numpy(),
            index=pd.to_datetime(raw["日期"]),
            name=symbol,
        )
    elif symbol == "000300.SH":
        series = _cn_csi300_close(start, end)
        return series
    elif symbol.endswith((".SH", ".SZ", ".BJ")):
        provider_symbol = symbol.split(".")[0]
        return _cn_equity_close(provider_symbol, symbol, start, end)
    else:
        raise ValueError(f"unsupported CN symbol {symbol}")
    return _slice_series_to_window(series, start, end)


class AkShareDataAdapter:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        return self._load_daily_impl(symbols, start, end)

    def _load_daily_impl(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()
        columns: dict[str, pd.Series] = {}
        workers = min(cn_market_data_max_workers(), len(symbols))

        def store(symbol: str, series: pd.Series) -> None:
            columns[symbol] = _slice_series_to_window(series, start, end)

        if workers <= 1 or len(symbols) == 1:
            for symbol in symbols:
                store(symbol, _fetch_cn_symbol_series(symbol, start, end))
            return pd.DataFrame(columns).sort_index()

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cn-daily") as pool:
            futures = {
                pool.submit(_fetch_cn_symbol_series, symbol, start, end): symbol
                for symbol in symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                store(symbol, future.result())
        return pd.DataFrame(columns).sort_index()


@dataclass(frozen=True, slots=True)
class RoutingDataAdapter:
    yahoo: YahooDataAdapter
    akshare: AkShareDataAdapter

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        if not symbols:
            from engine.research.data_errors import EmptySymbolsError

            raise EmptySymbolsError()
        is_cn = all(
            symbol == "CBA00101.CS"
            or symbol.startswith(("CN_BOND:", "CN_FUND:"))
            or symbol.endswith((".SH", ".SZ", ".BJ"))
            for symbol in symbols
        )

        def _load() -> pd.DataFrame:
            return (
                self.akshare.load_daily(symbols, start, end)
                if is_cn
                else self.yahoo.load_daily(symbols, start, end)
            )

        try:
            return run_with_deadline(
                _market_data_timeouts.MARKET_DATA_LOAD_TIMEOUT_SEC, _load
            )
        except TimeoutError:
            raise transient_data_error() from None


def gather(query: str, ports: tuple[MaterialPort, ...]) -> tuple[Material, ...]:
    materials = tuple(item for port in ports for item in port.fetch(query))
    seen: set[str] = set()
    unique = []
    for item in materials:
        if item.material_id not in seen:
            seen.add(item.material_id)
            unique.append(item)
    return tuple(unique)
