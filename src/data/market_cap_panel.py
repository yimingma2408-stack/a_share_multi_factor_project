from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.data.akshare_financials import (
    find_first_existing_column,
    normalize_ticker,
    read_universe,
    save_frame_with_fallback,
)


LOGGER = logging.getLogger(__name__)

MARKET_CAP_CANDIDATES = [
    "market_cap",
    "total_market_cap",
    "total_mv",
    "totalMarketValue",
    "总市值",
    "市价总值",
]
FLOAT_MARKET_CAP_CANDIDATES = [
    "float_market_cap",
    "circ_mv",
    "floatMarketValue",
    "流通市值",
]
DATE_CANDIDATES = ["date", "trade_date", "数据日期", "日期"]
TICKER_CANDIDATES = ["ticker", "code", "symbol", "股票代码", "代码"]


@dataclass
class MarketCapFetchResult:
    """Outcome of one ticker's historical market-cap request."""

    ticker: str
    status: str
    frame: pd.DataFrame
    source: str
    error_message: str


def read_market_cap_universe(project_root: Path) -> list[str]:
    """Read tickers using the required dynamic/clean/fundamental priority."""
    try:
        return read_universe(project_root)
    except FileNotFoundError:
        fundamental = project_root / "data/processed/fundamental_panel_akshare.parquet"
        if not fundamental.exists():
            raise FileNotFoundError(
                "No universe found in the dynamic HS300 panel, clean daily CSV, or AKShare fundamental panel."
            )
        frame = pd.read_parquet(fundamental, columns=["ticker"])
        return sorted({normalize_ticker(value) for value in frame["ticker"].dropna()})


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as exc:
            raise RuntimeError(
                f"Cannot read {path}: install pyarrow or fastparquet, or provide a CSV copy."
            ) from exc
    return pd.read_csv(path)


def _unit_rule(source_path: Path, source_field: str) -> tuple[float, str]:
    """Return an explicit source-field unit conversion to yuan."""
    field = str(source_field)
    if field in {"total_mv", "circ_mv"}:
        return 1e4, "万元 -> 元 (Tushare-style field convention)"
    if field in {"market_cap", "total_market_cap", "float_market_cap", "totalMarketValue", "floatMarketValue"}:
        return 1.0, "元 -> 元 (project field convention)"
    if field in {"总市值", "市价总值", "流通市值"}:
        if "industry_size_panel" in source_path.name:
            return 1.0, "元 -> 元 (existing project panel convention)"
        return 1.0, "assumed 元; source metadata should be reviewed"
    return 1.0, "unknown; no conversion applied"


def adapt_existing_market_cap(
    frame: pd.DataFrame,
    source_path: Path,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Adapt a pre-existing market-cap table to the unified schema."""
    date_col = find_first_existing_column(frame, DATE_CANDIDATES)
    ticker_col = find_first_existing_column(frame, TICKER_CANDIDATES)
    market_col = find_first_existing_column(frame, MARKET_CAP_CANDIDATES)
    float_col = find_first_existing_column(frame, FLOAT_MARKET_CAP_CANDIDATES)
    if date_col is None or ticker_col is None or market_col is None:
        raise ValueError(f"{source_path} lacks date, ticker, or total-market-cap fields")
    total_multiplier, total_rule = _unit_rule(source_path, market_col)
    if float_col:
        float_multiplier, float_rule = _unit_rule(source_path, float_col)
    else:
        float_multiplier, float_rule = 1.0, "unavailable"
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(frame[date_col], errors="coerce"),
            "ticker": frame[ticker_col].map(normalize_ticker),
            "market_cap": pd.to_numeric(frame[market_col], errors="coerce") * total_multiplier,
            "float_market_cap": (
                pd.to_numeric(frame[float_col], errors="coerce") * float_multiplier if float_col else np.nan
            ),
            "market_cap_source": f"existing_{source_path.stem}",
        }
    )
    out = out[out["date"].between(start_date, end_date)].dropna(subset=["date", "ticker"])
    metadata = {
        "source_field": market_col,
        "source_unit_rule": total_rule,
        "multiplier": total_multiplier,
        "float_source_field": float_col,
        "float_unit_rule": float_rule,
        "source_path": str(source_path),
    }
    return out.drop_duplicates(["date", "ticker"], keep="last"), metadata


def find_existing_market_cap_panel(
    project_root: Path,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, object]] | None:
    """Scan preferred and related processed tables for usable market-cap data."""
    processed = project_root / "data/processed"
    preferred = [
        processed / "industry_size_panel.parquet",
        processed / "industry_size_panel.csv",
        processed / "fundamental_panel.parquet",
        processed / "clean_daily_data.csv",
    ]
    related = sorted(processed.glob("*market*cap*.parquet")) + sorted(processed.glob("*market*cap*.csv"))
    excluded = {
        processed / "market_cap_panel.parquet",
        processed / "market_cap_panel.csv",
        processed / "fundamental_panel_akshare.parquet",
        processed / "fundamental_panel_akshare_with_market_cap.parquet",
    }
    for path in preferred + related:
        if path in excluded or not path.exists():
            continue
        try:
            adapted, metadata = adapt_existing_market_cap(_read_table(path), path, start_date, end_date)
            if adapted["market_cap"].notna().any():
                return adapted, metadata
        except (ValueError, RuntimeError, KeyError) as exc:
            LOGGER.info("Skipping existing table %s: %s", path, exc)
    return None


def _cached_market_cap(base_path: Path) -> tuple[pd.DataFrame, Path] | None:
    parquet_path = base_path.with_suffix(".parquet")
    csv_path = base_path.with_suffix(".csv")
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path), parquet_path
        except Exception as exc:
            LOGGER.warning("Ignoring unreadable market-cap cache %s: %s", parquet_path, exc)
    if csv_path.exists():
        try:
            return pd.read_csv(csv_path), csv_path
        except Exception as exc:
            LOGGER.warning("Ignoring unreadable market-cap cache %s: %s", csv_path, exc)
    return None


def _request_with_retries(call, description: str, retries: int, sleep_min: float, sleep_max: float) -> pd.DataFrame:
    errors = []
    for attempt in range(1, retries + 1):
        try:
            frame = call()
            if frame is None or frame.empty:
                raise RuntimeError("empty response")
            return frame
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            LOGGER.warning("%s failed (%s/%s): %s", description, attempt, retries, exc)
            if attempt < retries:
                time.sleep(random.uniform(sleep_min, sleep_max))
        finally:
            time.sleep(random.uniform(sleep_min, sleep_max))
    raise RuntimeError(" | ".join(errors))


def _normalize_stock_value_em(
    raw: pd.DataFrame,
    ticker: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Normalize stock_value_em output; AKShare documents both caps in yuan."""
    date_col = find_first_existing_column(raw, ["数据日期", "date", "TRADE_DATE"])
    market_col = find_first_existing_column(raw, ["总市值", "TOTAL_MARKET_CAP", "market_cap"])
    float_col = find_first_existing_column(raw, ["流通市值", "NOTLIMITED_MARKETCAP_A", "float_market_cap"])
    if date_col is None or market_col is None:
        raise ValueError("stock_value_em response lacks date or total market cap")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw[date_col], errors="coerce"),
            "ticker": normalize_ticker(ticker),
            "market_cap": pd.to_numeric(raw[market_col], errors="coerce"),
            "float_market_cap": pd.to_numeric(raw[float_col], errors="coerce") if float_col else np.nan,
            "market_cap_source": "akshare_stock_value_em",
        }
    )
    return out[out["date"].between(start_date, end_date)].dropna(subset=["date"]).drop_duplicates("date")


def _normalize_baidu_fallback(
    raw: pd.DataFrame,
    ticker: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Normalize Baidu values using an explicitly flagged inferred 1e8 multiplier."""
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["date"], errors="coerce"),
            "ticker": normalize_ticker(ticker),
            "market_cap": pd.to_numeric(raw["value"], errors="coerce") * 1e8,
            "float_market_cap": np.nan,
            "market_cap_source": "akshare_baidu_fallback_inferred_1e8",
        }
    )
    return out[out["date"].between(start_date, end_date)].dropna(subset=["date"]).drop_duplicates("date")


def fetch_market_cap_history(
    ticker: str,
    raw_root: Path,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    force: bool = False,
    retries: int = 3,
    sleep_min: float = 0.5,
    sleep_max: float = 2.0,
) -> MarketCapFetchResult:
    """Fetch historical daily caps from Eastmoney, with flagged Baidu fallback."""
    ticker = normalize_ticker(ticker)
    base = raw_root / f"{ticker}_market_cap"
    cached = _cached_market_cap(base)
    if cached is not None and not force:
        frame, _ = cached
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame[frame["date"].between(start_date, end_date)].copy()
        if not frame.empty and frame["date"].min() <= start_date:
            source = str(frame["market_cap_source"].dropna().iloc[0]) if len(frame) else "cached"
            return MarketCapFetchResult(ticker, "cached", frame, source, "")
        LOGGER.info("Cached market-cap data for %s starts after %s; refetching to try fallback fill", ticker, start_date.date())
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("AKShare is required. Install it with: pip install akshare") from exc

    errors = []
    try:
        raw = _request_with_retries(
            lambda: ak.stock_value_em(symbol=ticker),
            f"{ticker} stock_value_em",
            retries,
            sleep_min,
            sleep_max,
        )
        primary = _normalize_stock_value_em(raw, ticker, start_date, end_date)
        if primary.empty:
            raise RuntimeError("no Eastmoney rows in requested date range")
        frame = primary
        status = "success"
        source = "akshare_stock_value_em"
        if primary["date"].min() > start_date:
            try:
                fallback_raw = _request_with_retries(
                    lambda: ak.stock_zh_valuation_baidu(symbol=ticker, indicator="总市值", period="全部"),
                    f"{ticker} stock_zh_valuation_baidu",
                    retries,
                    sleep_min,
                    sleep_max,
                )
                fallback = _normalize_baidu_fallback(fallback_raw, ticker, start_date, primary["date"].min() - pd.Timedelta(days=1))
                if not fallback.empty:
                    frame = (
                        pd.concat([fallback, primary], ignore_index=True)
                        .sort_values(["date", "market_cap_source"])
                        .drop_duplicates("date", keep="last")
                    )
                    status = "success_with_fallback_fill"
                    source = "akshare_stock_value_em+akshare_baidu_fallback_inferred_1e8"
            except Exception as fallback_exc:
                errors.append(f"baidu_prefill: {fallback_exc}")
        save_frame_with_fallback(frame, base.with_suffix(".parquet"))
        return MarketCapFetchResult(ticker, status, frame, source, " | ".join(errors))
    except Exception as exc:
        errors.append(f"eastmoney: {exc}")

    try:
        raw = _request_with_retries(
            lambda: ak.stock_zh_valuation_baidu(symbol=ticker, indicator="总市值", period="全部"),
            f"{ticker} stock_zh_valuation_baidu",
            retries,
            sleep_min,
            sleep_max,
        )
        frame = _normalize_baidu_fallback(raw, ticker, start_date, end_date)
        if frame.empty:
            raise RuntimeError("no Baidu rows in requested date range")
        save_frame_with_fallback(frame, base.with_suffix(".parquet"))
        return MarketCapFetchResult(
            ticker,
            "fallback",
            frame,
            "akshare_baidu_fallback_inferred_1e8",
            " | ".join(errors),
        )
    except Exception as exc:
        errors.append(f"baidu: {exc}")
    empty = pd.DataFrame(columns=["date", "ticker", "market_cap", "float_market_cap", "market_cap_source"])
    return MarketCapFetchResult(ticker, "failed", empty, "", " | ".join(errors))


def align_to_project_trading_days(
    market_caps: pd.DataFrame,
    project_root: Path,
    tickers: Iterable[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, float]:
    """Keep project ticker/trading-day rows and backward-fill only past cap observations."""
    dynamic = project_root / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"
    clean = project_root / "data/processed/clean_daily_data.csv"
    if dynamic.exists():
        trades = pd.read_parquet(dynamic, columns=["date", "ticker"])
    elif clean.exists():
        trades = pd.read_csv(clean, usecols=["date", "ticker"])
    else:
        return market_caps.sort_values(["date", "ticker"]), float("nan")
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce").astype("datetime64[ns]")
    trades["ticker"] = trades["ticker"].map(normalize_ticker)
    wanted = set(tickers)
    trades = trades[
        trades["ticker"].isin(wanted) & trades["date"].between(start_date, end_date)
    ].drop_duplicates(["date", "ticker"])
    market_caps = market_caps.copy()
    market_caps["date"] = pd.to_datetime(market_caps["date"], errors="coerce").astype("datetime64[ns]")
    source_dates = market_caps[["date", "ticker"]].drop_duplicates()
    exact_alignment = float(
        trades.merge(source_dates.assign(exact=True), on=["date", "ticker"], how="left")["exact"].fillna(False).mean()
    )
    parts = []
    for ticker, dates in trades.groupby("ticker", sort=False):
        caps = market_caps[market_caps["ticker"].eq(ticker)].sort_values("date")
        if caps.empty:
            missing = dates.copy()
            missing["market_cap"] = np.nan
            missing["float_market_cap"] = np.nan
            missing["market_cap_source"] = np.nan
            missing["market_cap_observation_date"] = pd.NaT
            parts.append(missing)
            continue
        right = caps.rename(columns={"date": "market_cap_observation_date"})
        dates = dates.copy()
        dates["date"] = pd.to_datetime(dates["date"], errors="coerce").astype("datetime64[ns]")
        right["market_cap_observation_date"] = pd.to_datetime(
            right["market_cap_observation_date"], errors="coerce"
        ).astype("datetime64[ns]")
        matched = pd.merge_asof(
            dates.sort_values("date"),
            right.sort_values("market_cap_observation_date"),
            left_on="date",
            right_on="market_cap_observation_date",
            by="ticker",
            direction="backward",
        )
        parts.append(matched)
    panel = pd.concat(parts, ignore_index=True) if parts else market_caps.copy()
    return panel.sort_values(["date", "ticker"]).reset_index(drop=True), exact_alignment
