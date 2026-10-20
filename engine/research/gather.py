from __future__ import annotations

import calendar
import re
import threading
import warnings
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

import akshare as ak
import httpx
import pandas as pd
import yfinance as yf

from engine.research import market_data_timeouts as _market_data_timeouts
from engine.research.data_availability import market_data_timeout
from engine.research.market_data_progress import (
    clear_market_data_progress,
    set_market_data_progress,
)
from engine.research.market_data_cancel import (
    bind_market_data_generation,
    current_market_data_generation,
    end_market_data_generation,
    install_market_data_request_guard,
    raise_if_market_data_cancelled,
)
from engine.research.market_data_retry import (
    call_with_rate_limit_retry,
    call_with_symbol_retry,
    is_rate_limited,
)
from engine.research.market_data_timeouts import (
    CN_HTTP_TIMEOUT_SEC,
    YAHOO_BATCH_SIZE,
    YAHOO_FETCH_CONCURRENCY,
    cn_market_data_max_workers,
    load_deadline_seconds,
    run_with_deadline,
)
from engine.research.planned_data_window import is_cn_listed_symbol
from engine.research.price_cache import get_cached_close, put_cached_close
from engine.research.secret_redaction import redact_text

CROSSREF_MAILTO = "research@example.invalid"
_PUBLISHED_HEADER = re.compile(r"published:\s*(\d{4}-\d{2}-\d{2})\s*$", re.IGNORECASE)


def parse_crossref_issued(issued: object) -> tuple[date, str] | None:
    """Parse Crossref ``issued.date-parts``. ``created`` is not a fallback.

    Returns ``(date, precision)`` where precision is ``year``, ``year_month``,
    or ``day``. Year only → 31 Dec. Year and month → month end.
    Missing or unparseable → None.
    """
    if not isinstance(issued, dict):
        return None
    parts = issued.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    numbers: list[int] = []
    for raw in parts[0][:3]:
        if raw is None:
            break
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None
        numbers.append(raw)
    if not numbers:
        return None
    year = numbers[0]
    if year < 1 or year > 9999:
        return None
    if len(numbers) == 1:
        return date(year, 12, 31), "year"
    month = numbers[1]
    if not 1 <= month <= 12:
        return None
    if len(numbers) == 2:
        return date(year, month, calendar.monthrange(year, month)[1]), "year_month"
    try:
        return date(year, month, numbers[2]), "day"
    except ValueError:
        return None


def published_at_from_crossref_issued(issued: object) -> date | None:
    parsed = parse_crossref_issued(issued)
    return None if parsed is None else parsed[0]


def published_at_from_markdown(text: str) -> date | None:
    """Read ``published: YYYY-MM-DD`` from YAML front matter only. Never file mtime."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = _PUBLISHED_HEADER.match(line.strip())
        if match is None:
            continue
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            return None
    return None


@dataclass(frozen=True, slots=True)
class Material:
    material_id: str
    source: str
    title: str
    url: str
    text: str
    fetched_at: datetime
    published_at: date | None = None
    published_precision: str | None = None


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
    mailto: str = CROSSREF_MAILTO
    fetch_errors: list[str] = field(default_factory=list)

    def fetch(self, query: str) -> tuple[Material, ...]:
        try:
            response = self.client.get(
                "https://api.crossref.org/works",
                params={
                    "query": query,
                    "rows": 5,
                    "select": "DOI,title,URL,abstract,issued",
                    "mailto": self.mailto,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            items = response.json()["message"]["items"]
        except Exception as exc:  # noqa: BLE001 — material fetch must not abort research
            self.fetch_errors.append(f"crossref: {type(exc).__name__}: {exc}")
            return ()
        result = []
        for item in items:
            doi = item.get("DOI")
            if not isinstance(doi, str) or not doi:
                self.fetch_errors.append("crossref: missing DOI")
                continue
            title = " ".join(item.get("title", ["Untitled"]))
            parsed = parse_crossref_issued(item.get("issued"))
            result.append(
                Material(
                    material_id=f"doi:{doi}",
                    source="papers",
                    title=title,
                    url=item.get("URL", f"https://doi.org/{doi}"),
                    text=item.get("abstract", title),
                    fetched_at=self.now(),
                    published_at=None if parsed is None else parsed[0],
                    published_precision=None if parsed is None else parsed[1],
                )
            )
        return tuple(result)


@dataclass(slots=True)
class SecEdgarAdapter:
    client: httpx.Client
    now: Callable[[], datetime]
    user_agent: str
    fetch_errors: list[str] = field(default_factory=list)

    def fetch(self, query: str) -> tuple[Material, ...]:
        try:
            response = self.client.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": self.user_agent},
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 — material fetch must not abort research
            self.fetch_errors.append(f"sec-edgar: {type(exc).__name__}: {exc}")
            return ()
        matches = []
        for item in payload.values():
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
                        published_at=None,
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
                published = published_at_from_markdown(text)
                result.append(
                    Material(
                        material_id=f"local:{path.name}",
                        source="local",
                        title=path.stem,
                        url=path.resolve().as_uri(),
                        text=text,
                        fetched_at=self.now(),
                        published_at=published,
                        published_precision="day" if published is not None else None,
                    )
                )
        return tuple(result)


def _yahoo_provider_symbol(symbol: str) -> str:
    return "^GSPC" if symbol == "SPX" else symbol


def _yahoo_batches(symbols: tuple[str, ...], batch_size: int) -> tuple[tuple[str, ...], ...]:
    size = max(1, batch_size)
    return tuple(symbols[index : index + size] for index in range(0, len(symbols), size))


_retry_after_local = threading.local()
_yahoo_capture_installed = False
_yahoo_capture_lock = threading.Lock()


class _RetryAfterRateLimit(Exception):
    """429 that still carries the Retry-After yfinance drops from YFRateLimitError."""

    def __init__(self, retry_after: object) -> None:
        headers: dict[str, str] = {}
        if retry_after is not None and str(retry_after).strip():
            headers["Retry-After"] = str(retry_after).strip()
        self.response = type("Resp", (), {"status_code": 429, "headers": headers})()
        super().__init__("HTTP 429")


def _note_retry_after(response: object) -> None:
    if getattr(response, "status_code", None) != 429:
        return
    headers = getattr(response, "headers", None)
    raw = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
    _retry_after_local.value = raw


def _install_yahoo_retry_after_capture() -> None:
    """Wrap each Yahoo session so a 429 keeps its Retry-After header.

    ``yfinance`` raises ``YFRateLimitError()`` with no response, and ``download()``
    then stores that per ticker and returns an empty frame. Chart requests go
    through ``Ticker.history`` instead, and this wrapper reads the header first.
    """
    global _yahoo_capture_installed
    with _yahoo_capture_lock:
        if _yahoo_capture_installed:
            return
        from yfinance.data import YfData

        original = YfData._set_session

        def _set_session(self: object, session: object) -> None:
            original(self, session)
            if session is None or getattr(session, "_alphaloop_retry_after", False):
                return
            original_get = session.get

            def get(*args: object, **kwargs: object) -> object:
                response = original_get(*args, **kwargs)
                _note_retry_after(response)
                return response

            session.get = get  # type: ignore[method-assign]
            session._alphaloop_retry_after = True  # type: ignore[attr-defined]

        YfData._set_session = _set_session  # type: ignore[method-assign]
        _yahoo_capture_installed = True


def _empty_close(symbol: str) -> pd.Series:
    return pd.Series(dtype="float64", name=symbol)


def _yahoo_history(symbol: str, start: date, end: date) -> pd.Series:
    """One chart request. Missing prices stay empty; 429 keeps Retry-After."""
    raise_if_market_data_cancelled()
    _install_yahoo_retry_after_capture()
    _retry_after_local.value = None
    provider = _yahoo_provider_symbol(symbol)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            frame = yf.Ticker(provider).history(
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
                actions=False,
                raise_errors=True,
            )
    except Exception as error:
        if _is_missing_yahoo_prices(error):
            if is_rate_limited(error):
                raise _RetryAfterRateLimit(getattr(_retry_after_local, "value", None)) from error
            return _empty_close(symbol)
        if is_rate_limited(error):
            raise _RetryAfterRateLimit(getattr(_retry_after_local, "value", None)) from error
        raise
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or "Close" not in frame.columns:
        return _empty_close(symbol)
    series = pd.Series(frame["Close"].to_numpy(), index=pd.to_datetime(frame.index), name=symbol)
    if getattr(series.index, "tz", None) is not None:
        series.index = series.index.tz_localize(None)
    return series


def _is_missing_yahoo_prices(error: BaseException) -> bool:
    name = type(error).__name__
    return name in {"YFPricesMissingError", "YFTzMissingError"}


class YahooDataAdapter:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()
        set_market_data_progress(0, len(symbols), "yahoo")
        try:
            cached: dict[str, pd.Series] = {}
            missing: list[str] = []
            for symbol in symbols:
                hit = get_cached_close("yahoo", symbol, start, end)
                if hit is None:
                    missing.append(symbol)
                else:
                    cached[symbol] = hit
            done = len(cached)
            set_market_data_progress(done, len(symbols), "yahoo")
            fetched: dict[str, pd.Series] = {}

            def advance() -> None:
                nonlocal done
                done += 1
                set_market_data_progress(done, len(symbols), "yahoo")

            for batch in _yahoo_batches(tuple(missing), YAHOO_BATCH_SIZE):
                frame = self._download_batch(batch, start, end, on_symbol_done=advance)
                for symbol in batch:
                    if symbol in frame.columns and frame[symbol].notna().any():
                        fetched[symbol] = frame[symbol].rename(symbol)
            columns = {symbol: cached.get(symbol, fetched.get(symbol)) for symbol in symbols}
            present = {symbol: series for symbol, series in columns.items() if series is not None}
            if not present:
                return pd.DataFrame()
            return pd.DataFrame(present).sort_index()
        finally:
            clear_market_data_progress()

    def _download_batch(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
        on_symbol_done: Callable[[], None] | None = None,
    ) -> pd.DataFrame:
        """Fetch one batch, two chart calls at a time, and cache each success.

        ``yf.download`` swallows HTTP 429 into an empty column. Per-symbol
        ``history`` lets the retry see the error. A symbol with no prices is
        left out so confirm can drop just that name; a 429 or other failure
        aborts the load instead of looking like a smaller pool.
        """
        columns: dict[str, pd.Series] = {}

        generation = current_market_data_generation()

        def fetch(symbol: str) -> pd.Series | None:
            token = bind_market_data_generation(generation)
            try:
                raise_if_market_data_cancelled()

                def once() -> pd.Series:
                    return call_with_rate_limit_retry(
                        lambda symbol=symbol: _yahoo_history(symbol, start, end)
                    )

                series = call_with_symbol_retry(once, symbol=symbol)
            finally:
                end_market_data_generation(token)
            if series is None or not series.notna().any():
                return None
            put_cached_close("yahoo", symbol, start, end, series)
            return series

        def mark(symbol: str, series: pd.Series | None) -> None:
            if series is not None:
                columns[symbol] = series
            if on_symbol_done is not None:
                on_symbol_done()

        workers = min(YAHOO_FETCH_CONCURRENCY, len(symbols))
        if workers <= 1:
            for symbol in symbols:
                mark(symbol, fetch(symbol))
        else:
            pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="yahoo-daily")
            try:
                futures = {pool.submit(fetch, symbol): symbol for symbol in symbols}
                for future in as_completed(futures):
                    raise_if_market_data_cancelled()
                    symbol = futures[future]
                    mark(symbol, future.result())
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        if not columns:
            return pd.DataFrame()
        return pd.DataFrame(columns)


def _sina_listing_code(symbol: str, provider_symbol: str) -> str:
    if symbol.endswith(".SH"):
        return f"sh{provider_symbol}"
    if symbol.endswith(".SZ"):
        return f"sz{provider_symbol}"
    if symbol.endswith(".BJ"):
        return f"bj{provider_symbol}"
    return f"sh{provider_symbol}"


def _is_transport_timeout(error: BaseException) -> bool:
    name = type(error).__name__.lower()
    if "timeout" in name:
        return True
    text = str(error).lower()
    return "timed out" in text or "timeout" in text


def _cn_equity_close(provider_symbol: str, symbol: str, start: date, end: date) -> pd.Series:
    """A-share daily close: Sina (akshare) first, Eastmoney akshare fallback."""
    raise_if_market_data_cancelled()
    install_market_data_request_guard()
    sina_code = _sina_listing_code(symbol, provider_symbol)
    try:
        raw = ak.stock_zh_a_daily(symbol=sina_code, adjust="qfq")
        series = pd.Series(
            raw["close"].to_numpy(),
            index=pd.to_datetime(raw["date"]),
            name=symbol,
        )
        return series.loc[start.isoformat() : end.isoformat()]
    except Exception as error:
        if is_rate_limited(error) or _is_transport_timeout(error):
            raise
        raw = ak.stock_zh_a_hist(
            symbol=provider_symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
            timeout=CN_HTTP_TIMEOUT_SEC,
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
    except Exception as error:
        if is_rate_limited(error):
            raise
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
        install_market_data_request_guard()
        set_market_data_progress(0, len(symbols), "akshare")
        try:
            columns: dict[str, pd.Series] = {}
            missing: list[str] = []
            for symbol in symbols:
                hit = get_cached_close("akshare", symbol, start, end)
                if hit is None:
                    missing.append(symbol)
                else:
                    columns[symbol] = hit
            done = len(columns)
            set_market_data_progress(done, len(symbols), "akshare")
            if missing:
                fetched = self._fetch_missing(tuple(missing), start, end, done, len(symbols))
                columns.update(fetched)
            if not columns:
                return pd.DataFrame()
            return pd.DataFrame({symbol: columns[symbol] for symbol in symbols if symbol in columns}).sort_index()
        finally:
            clear_market_data_progress()

    def _fetch_missing(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
        done: int,
        total: int,
    ) -> dict[str, pd.Series]:
        columns: dict[str, pd.Series] = {}
        workers = min(cn_market_data_max_workers(), len(symbols))

        generation = current_market_data_generation()

        def fetch(symbol: str) -> pd.Series:
            token = bind_market_data_generation(generation)
            try:
                raise_if_market_data_cancelled()

                def once() -> pd.Series:
                    return call_with_rate_limit_retry(
                        lambda symbol=symbol: _fetch_cn_symbol_series(symbol, start, end)
                    )

                series = call_with_symbol_retry(once, symbol=symbol)
            finally:
                end_market_data_generation(token)
            put_cached_close("akshare", symbol, start, end, series)
            return series

        if workers <= 1 or len(symbols) == 1:
            for symbol in symbols:
                columns[symbol] = fetch(symbol)
                done += 1
                set_market_data_progress(done, total, "akshare")
            return columns

        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cn-daily")
        try:
            futures = {pool.submit(fetch, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                raise_if_market_data_cancelled()
                symbol = futures[future]
                columns[symbol] = future.result()
                done += 1
                set_market_data_progress(done, total, "akshare")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return columns


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
        is_cn = all(is_cn_listed_symbol(symbol) for symbol in symbols)

        def _load() -> pd.DataFrame:
            return (
                self.akshare.load_daily(symbols, start, end)
                if is_cn
                else self.yahoo.load_daily(symbols, start, end)
            )

        batch = (
            cn_market_data_max_workers()
            if is_cn
            else _market_data_timeouts.YAHOO_BATCH_SIZE
        )
        try:
            return run_with_deadline(load_deadline_seconds(len(symbols), batch_size=batch), _load)
        except TimeoutError:
            raise market_data_timeout(len(symbols)) from None


@dataclass(frozen=True, slots=True)
class GatherBatch:
    materials: tuple[Material, ...]
    failures: tuple[str, ...]


def gather_materials(query: str, ports: tuple[MaterialPort, ...]) -> GatherBatch:
    """Fetch every port. A failed port is recorded and does not abort the others."""
    collected: list[Material] = []
    failures: list[str] = []
    for port in ports:
        try:
            collected.extend(port.fetch(query))
        except Exception as exc:  # noqa: BLE001 — material fetch must not abort research
            failures.append(redact_text(f"{type(port).__name__}: {type(exc).__name__}: {exc}"))
            continue
        extra = getattr(port, "fetch_errors", ())
        failures.extend(str(item) for item in extra)
    seen: set[str] = set()
    unique: list[Material] = []
    for item in collected:
        if item.material_id not in seen:
            seen.add(item.material_id)
            unique.append(item)
    return GatherBatch(tuple(unique), tuple(failures))


def gather(query: str, ports: tuple[MaterialPort, ...]) -> tuple[Material, ...]:
    return gather_materials(query, ports).materials


def pit_evidence_from_payloads(
    payloads: tuple[object, ...],
    *,
    revision: str,
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...], tuple[str, ...]]:
    """Return ``(evidence_as_of, missing_as_of, undated_excluded)``.

    pit-v1 keeps the legacy rule: every saved material is missing ``as_of``.
    pit-v2 cites only a real ``published_at`` and lists the rest as not used.
    """
    from engine.verifiers import PIT_REVISION_V2

    rows: list[Mapping[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            raise TypeError("evidence file must be a JSON object")
        rows.append(item)
    if revision != PIT_REVISION_V2:
        missing = tuple(str(item["material_id"]) for item in rows)
        return (), missing, ()
    dated: list[tuple[str, str]] = []
    undated: list[str] = []
    for item in rows:
        material_id = str(item["material_id"])
        published = item.get("published_at")
        if isinstance(published, str) and published:
            dated.append((material_id, published))
        else:
            undated.append(material_id)
    return tuple(dated), (), tuple(undated)


def pit_evidence_annotations(payloads: tuple[object, ...]) -> tuple[tuple[str, str, str], ...]:
    """``(material_id, title, published_precision)`` for pit-v2 display. pit-v1 ignores this."""
    annotations: list[tuple[str, str, str]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        annotations.append(
            (
                str(item.get("material_id") or ""),
                str(item.get("title") or ""),
                str(item.get("published_precision") or ""),
            )
        )
    return tuple(annotations)
