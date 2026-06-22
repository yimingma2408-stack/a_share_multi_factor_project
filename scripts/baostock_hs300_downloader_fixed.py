from __future__ import annotations

from pathlib import Path
from typing import Iterable
import random
import time

import baostock as bs
import pandas as pd


# =========================================================
# Paths and global settings
# =========================================================

try:    
    PROJECT_DIR = Path(__file__).resolve().parents[1]
except NameError:  # Jupyter / interactive mode
    PROJECT_DIR = Path.cwd()

RAW_DIR = PROJECT_DIR / "data" / "raw"
MARKET_DIR = RAW_DIR / "market"
FACTOR_DIR = RAW_DIR / "adjust_factor"
UNIVERSE_DIR = RAW_DIR / "universe"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

for folder in [RAW_DIR, MARKET_DIR, FACTOR_DIR, UNIVERSE_DIR, PROCESSED_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

START_DATE = "2016-01-01"
END_DATE = "2025-12-31"
DATA_SOURCE = "baostock"
MAX_RETRIES = 3
REQUEST_SLEEP = 0.25

_BAOSTOCK_LOGGED_IN = False


# =========================================================
# Login
# =========================================================

def baostock_login() -> None:
    global _BAOSTOCK_LOGGED_IN
    if _BAOSTOCK_LOGGED_IN:
        return

    result = bs.login()
    print("BaoStock login:", result.error_code, result.error_msg)
    if result.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {result.error_msg}")

    _BAOSTOCK_LOGGED_IN = True


def baostock_logout() -> None:
    global _BAOSTOCK_LOGGED_IN
    if _BAOSTOCK_LOGGED_IN:
        bs.logout()
        _BAOSTOCK_LOGGED_IN = False


# =========================================================
# Helpers
# =========================================================

def normalize_date(value: str | int | pd.Timestamp) -> str:
    return pd.Timestamp(str(value)).strftime("%Y-%m-%d")


def date_key(value: str | int | pd.Timestamp) -> str:
    return pd.Timestamp(normalize_date(value)).strftime("%Y%m%d")


def stock_code_to_baostock_code(stock_code: str) -> str:
    stock_code = str(stock_code).strip().zfill(6)

    if stock_code.startswith(("5", "6", "9")):
        return f"sh.{stock_code}"
    if stock_code.startswith(("0", "1", "2", "3")):
        return f"sz.{stock_code}"
    if stock_code.startswith(("4", "8")):
        return f"bj.{stock_code}"

    raise ValueError(f"Unsupported security code: {stock_code}")


def baostock_code_to_ticker(code: str) -> str:
    return str(code).split(".")[-1].zfill(6)


def adjust_to_flag(adjust: str) -> str:
    adjust = adjust.lower().strip()
    mapping = {
        "hfq": "1",
        "backward": "1",
        "qfq": "2",
        "forward": "2",
        "none": "3",
        "raw": "3",
        "bfq": "3",
        "": "3",
    }
    if adjust not in mapping:
        raise ValueError(f"Unknown adjust type: {adjust}")
    return mapping[adjust]


def result_to_dataframe(result) -> pd.DataFrame:
    if result.error_code != "0":
        raise RuntimeError(
            f"BaoStock error_code={result.error_code}, "
            f"error_msg={result.error_msg}"
        )

    rows = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=result.fields)


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def deduplicate_market(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return (
        df.sort_values(["ticker", "date"])
        .drop_duplicates(["ticker", "date"], keep="last")
        .reset_index(drop=True)
    )


def query_with_retry(func, label: str, max_retries: int = MAX_RETRIES):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            print(f"[{label}] attempt {attempt}/{max_retries} failed: {exc}")
            if attempt < max_retries:
                time.sleep(2 + random.random())
    raise RuntimeError(f"[{label}] failed after {max_retries} attempts") from last_error


# =========================================================
# Trading calendar
# =========================================================

def get_trade_calendar(
    start_date: str,
    end_date: str,
    force_download: bool = False,
) -> pd.DataFrame:
    baostock_login()
    start_date = normalize_date(start_date)
    end_date = normalize_date(end_date)

    path = RAW_DIR / (
        f"trade_calendar_{date_key(start_date)}_{date_key(end_date)}.parquet"
    )
    if path.exists() and not force_download:
        return pd.read_parquet(path)

    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    df = result_to_dataframe(rs)
    if df.empty:
        raise RuntimeError("Empty trading calendar returned")

    df = df.rename(columns={"calendar_date": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df["is_trading_day"] = pd.to_numeric(
        df["is_trading_day"], errors="coerce"
    ).astype("Int64")
    save_parquet(df, path)
    return df


def get_month_end_trading_dates(calendar: pd.DataFrame) -> list[pd.Timestamp]:
    trading = calendar.loc[calendar["is_trading_day"].eq(1), ["date"]].copy()
    trading["month"] = trading["date"].dt.to_period("M")
    return trading.groupby("month")["date"].max().sort_values().tolist()


# =========================================================
# Fix 1: dynamic historical HS300 universe
# =========================================================

def query_hs300_snapshot(index_date: str) -> pd.DataFrame:
    """
    Query HS300 constituents on a specified date.

    Never silently fall back to the latest constituents. Such a fallback would
    create a mislabeled and forward-looking universe.
    """
    baostock_login()
    index_date = normalize_date(index_date)

    try:
        rs = bs.query_hs300_stocks(date=index_date)
    except TypeError as exc:
        raise RuntimeError(
            "This BaoStock version does not support "
            "query_hs300_stocks(date=...). Upgrade BaoStock; "
            "the latest constituents cannot replace historical constituents."
        ) from exc

    df = result_to_dataframe(rs)
    if df.empty:
        raise RuntimeError(f"Empty HS300 constituent result for {index_date}")
    if "code" not in df.columns:
        raise ValueError(f"Missing code column: {list(df.columns)}")

    df["query_date"] = pd.Timestamp(index_date)
    source_date_col = next(
        (c for c in ["updateDate", "date"] if c in df.columns), None
    )
    df["source_update_date"] = (
        pd.to_datetime(df[source_date_col], errors="coerce")
        if source_date_col
        else pd.NaT
    )
    df["ticker"] = df["code"].map(baostock_code_to_ticker)
    df["is_hs300_member"] = True

    columns = [
        "query_date",
        "source_update_date",
        "code",
        "ticker",
        "is_hs300_member",
    ]
    if "code_name" in df.columns:
        columns.append("code_name")

    return (
        df[columns]
        .drop_duplicates(["query_date", "ticker"])
        .sort_values(["query_date", "ticker"])
        .reset_index(drop=True)
    )


def build_hs300_monthly_universe(
    start_date: str,
    end_date: str,
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Query one HS300 snapshot at every month-end trading date.

    Monthly snapshots are much safer than using one static 2025 constituent
    list for the entire 2016-2025 period. If exact index adjustment effective
    dates become available later, replace these monthly snapshots with them.
    """
    start_date = normalize_date(start_date)
    end_date = normalize_date(end_date)
    path = UNIVERSE_DIR / (
        f"hs300_monthly_{date_key(start_date)}_{date_key(end_date)}.parquet"
    )

    if path.exists() and not force_download:
        return pd.read_parquet(path)

    calendar = get_trade_calendar(start_date, end_date)
    dates = get_month_end_trading_dates(calendar)
    snapshots = []

    for i, dt in enumerate(dates, start=1):
        date_str = dt.strftime("%Y-%m-%d")
        print(f"[HS300] snapshot {i}/{len(dates)}: {date_str}")
        snapshot = query_with_retry(
            lambda d=date_str: query_hs300_snapshot(d),
            label=f"HS300 {date_str}",
        )
        snapshots.append(snapshot)
        time.sleep(REQUEST_SLEEP + random.random() * 0.2)

    universe = pd.concat(snapshots, ignore_index=True)
    universe = (
        universe.sort_values(["query_date", "ticker"])
        .drop_duplicates(["query_date", "ticker"])
        .reset_index(drop=True)
    )
    save_parquet(universe, path)
    return universe


def historical_union_symbols(universe: pd.DataFrame) -> list[str]:
    return sorted(
        universe["ticker"].dropna().astype(str).str.zfill(6).unique().tolist()
    )


def attach_membership(panel: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Attach the latest available monthly membership snapshot to each date."""
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    snapshot_dates = (
        universe[["query_date"]]
        .drop_duplicates()
        .rename(columns={"query_date": "snapshot_date"})
        .sort_values("snapshot_date")
    )
    snapshot_dates["snapshot_date"] = pd.to_datetime(
        snapshot_dates["snapshot_date"]
    )

    unique_dates = panel[["date"]].drop_duplicates().sort_values("date")
    date_map = pd.merge_asof(
        unique_dates,
        snapshot_dates,
        left_on="date",
        right_on="snapshot_date",
        direction="backward",
    )
    panel = panel.merge(date_map, on="date", how="left")

    members = universe[["query_date", "ticker"]].copy()
    members = members.rename(columns={"query_date": "snapshot_date"})
    members["snapshot_date"] = pd.to_datetime(members["snapshot_date"])
    members["ticker"] = members["ticker"].astype(str).str.zfill(6)
    members["is_hs300_member"] = True

    panel = panel.merge(
        members,
        on=["snapshot_date", "ticker"],
        how="left",
    )
    panel["is_hs300_member"] = (
        panel["is_hs300_member"].fillna(False).astype(bool)
    )
    return panel.drop(columns="snapshot_date")


# =========================================================
# Market data
# =========================================================

def query_market_data(
    stock_code: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> pd.DataFrame:
    baostock_login()

    stock_code = str(stock_code).zfill(6)
    rs = bs.query_history_k_data_plus(
        code=stock_code_to_baostock_code(stock_code),
        fields=(
            "date,code,open,high,low,close,preclose,volume,amount,"
            "adjustflag,turn,tradestatus,pctChg,isST"
        ),
        start_date=normalize_date(start_date),
        end_date=normalize_date(end_date),
        frequency="d",
        adjustflag=adjust_to_flag(adjust),
    )
    df = result_to_dataframe(rs)
    if df.empty:
        return df

    df = df.rename(
        columns={
            "code": "ticker",
            "preclose": "pre_close",
            "turn": "turnover",
            "tradestatus": "trade_status",
            "pctChg": "pct_change_pct",
            "isST": "is_st",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].map(baostock_code_to_ticker)
    df["adjust_type"] = adjust

    numeric_cols = [
        "open", "high", "low", "close", "pre_close", "volume",
        "amount", "turnover", "pct_change_pct", "trade_status", "is_st",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fix 3: retain suspended and ST records; filter only in research layer.
    df["trade_status"] = df["trade_status"].astype("Int64")
    df["is_st"] = df["is_st"].astype("Int64")
    df["return_vendor"] = df["pct_change_pct"] / 100.0

    return deduplicate_market(df)


def market_cache_path(stock_code: str, adjust: str) -> Path:
    return MARKET_DIR / (
        f"{str(stock_code).zfill(6)}_daily_{adjust}_{DATA_SOURCE}.parquet"
    )


def requested_missing_ranges(
    cached: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> list[tuple[str, str]]:
    """Return only missing left/right edge ranges of a continuous cache."""
    start = pd.Timestamp(normalize_date(start_date))
    end = pd.Timestamp(normalize_date(end_date))
    if start > end:
        raise ValueError("start_date is later than end_date")

    if cached.empty or "date" not in cached.columns:
        return [(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))]

    dates = pd.to_datetime(cached["date"], errors="coerce").dropna()
    if dates.empty:
        return [(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))]

    cached_start, cached_end = dates.min(), dates.max()
    ranges = []

    if start < cached_start:
        left_end = cached_start - pd.Timedelta(days=1)
        ranges.append((start.strftime("%Y-%m-%d"), left_end.strftime("%Y-%m-%d")))
    if end > cached_end:
        right_start = cached_end + pd.Timedelta(days=1)
        ranges.append((right_start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))

    return ranges


def load_or_update_market_data(
    stock_code: str,
    start_date: str,
    end_date: str,
    adjust: str,
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Fix 2: cache is updated when the requested date range expands.
    """
    stock_code = str(stock_code).zfill(6)
    start_date = normalize_date(start_date)
    end_date = normalize_date(end_date)
    path = market_cache_path(stock_code, adjust)

    cached = pd.DataFrame()
    if path.exists() and not force_download:
        cached = pd.read_parquet(path)
        if not cached.empty:
            cached["date"] = pd.to_datetime(cached["date"])
            cached["ticker"] = cached["ticker"].astype(str).str.zfill(6)

    ranges = (
        [(start_date, end_date)]
        if force_download
        else requested_missing_ranges(cached, start_date, end_date)
    )
    if force_download:
        cached = pd.DataFrame()

    new_parts = []
    for range_start, range_end in ranges:
        print(f"[{stock_code}][{adjust}] {range_start} -> {range_end}")
        part = query_with_retry(
            lambda: query_market_data(
                stock_code, range_start, range_end, adjust
            ),
            label=f"{stock_code} {adjust}",
        )
        if not part.empty:
            new_parts.append(part)

    parts = [x for x in [cached, *new_parts] if not x.empty]
    if not parts:
        return pd.DataFrame()

    combined = deduplicate_market(pd.concat(parts, ignore_index=True))
    save_parquet(combined, path)

    mask = combined["date"].between(
        pd.Timestamp(start_date), pd.Timestamp(end_date)
    )
    return combined.loc[mask].reset_index(drop=True)


# =========================================================
# Optional adjustment factors
# =========================================================

def query_adjust_factors_optional(
    stock_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Query independent adjustment factors when BaoStock supplies them.

    This is optional because the officially documented coverage is old. The
    main pipeline therefore also downloads raw and qfq prices independently.
    """
    baostock_login()
    stock_code = str(stock_code).zfill(6)

    rs = bs.query_adjust_factor(
        code=stock_code_to_baostock_code(stock_code),
        start_date=normalize_date(start_date),
        end_date=normalize_date(end_date),
    )
    df = result_to_dataframe(rs)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "date", "ticker", "fore_adjust_factor",
                "back_adjust_factor", "adjust_factor",
            ]
        )

    rename_map = {
        "code": "ticker",
        "dividOperateDate": "date",
        "foreAdjustFactor": "fore_adjust_factor",
        "backAdjustFactor": "back_adjust_factor",
        "adjustFactor": "adjust_factor",
    }
    df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise ValueError(
            f"Unrecognized adjustment factor columns: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ticker"] = df["ticker"].map(baostock_code_to_ticker)

    factor_cols = [
        "fore_adjust_factor", "back_adjust_factor", "adjust_factor"
    ]
    for col in factor_cols:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return (
        df[["date", "ticker", *factor_cols]]
        .dropna(subset=["date"])
        .drop_duplicates(["ticker", "date"], keep="last")
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )


def load_adjust_factors_optional(
    stock_code: str,
    start_date: str,
    end_date: str,
    force_download: bool = False,
) -> pd.DataFrame:
    path = FACTOR_DIR / (
        f"{str(stock_code).zfill(6)}_adjust_factor_{DATA_SOURCE}.parquet"
    )
    if path.exists() and not force_download:
        return pd.read_parquet(path)

    try:
        df = query_with_retry(
            lambda: query_adjust_factors_optional(
                stock_code, start_date, end_date
            ),
            label=f"{stock_code} adjust-factor",
        )
    except Exception as exc:
        print(f"[{stock_code}] adjustment factors unavailable: {exc}")
        return pd.DataFrame()

    if not df.empty:
        save_parquet(df, path)
    return df


# =========================================================
# Build per-stock table
# =========================================================

def merge_sparse_factors(
    market: pd.DataFrame,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    factor_cols = [
        "fore_adjust_factor", "back_adjust_factor", "adjust_factor"
    ]
    if factors.empty:
        for col in factor_cols:
            market[col] = pd.NA
        return market

    factors = factors.sort_values("date")
    return pd.merge_asof(
        market.sort_values("date"),
        factors[["date", *factor_cols]].sort_values("date"),
        on="date",
        direction="backward",
    )


def build_one_stock_table(
    stock_code: str,
    start_date: str,
    end_date: str,
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Fix 4: save raw and qfq prices separately, plus optional factor fields.
    """
    raw = load_or_update_market_data(
        stock_code, start_date, end_date, "none", force_download
    )
    qfq = load_or_update_market_data(
        stock_code, start_date, end_date, "qfq", force_download
    )
    factors = load_adjust_factors_optional(
        stock_code, start_date, end_date, force_download
    )

    if raw.empty and qfq.empty:
        return pd.DataFrame()

    raw_cols = [
        "date", "ticker", "open", "high", "low", "close",
        "volume", "amount", "turnover", "pct_change_pct",
        "trade_status", "is_st",
    ]
    qfq_cols = ["date", "ticker", "open", "high", "low", "close"]

    raw = raw[raw_cols].rename(
        columns={
            "open": "raw_open", "high": "raw_high",
            "low": "raw_low", "close": "raw_close",
        }
    )
    qfq = qfq[qfq_cols].rename(
        columns={
            "open": "qfq_open", "high": "qfq_high",
            "low": "qfq_low", "close": "qfq_close",
        }
    )

    table = raw.merge(qfq, on=["date", "ticker"], how="outer")
    table = table.sort_values(["ticker", "date"]).reset_index(drop=True)
    table = merge_sparse_factors(table, factors)

    table["return_1d"] = (
        table.groupby("ticker")["qfq_close"]
        .pct_change(fill_method=None)
    )
    table["return_vendor"] = table["pct_change_pct"] / 100.0
    return table


# =========================================================
# Panel
# =========================================================

def download_stock_panel(
    symbols: Iterable[str],
    start_date: str,
    end_date: str,
    universe: pd.DataFrame,
    force_download: bool = False,
) -> pd.DataFrame:
    symbols = sorted({str(x).zfill(6) for x in symbols})
    frames = []

    for i, symbol in enumerate(symbols, start=1):
        print("=" * 80)
        print(f"Processing {i}/{len(symbols)}: {symbol}")
        try:
            df = build_one_stock_table(
                symbol, start_date, end_date, force_download
            )
        except Exception as exc:
            print(f"[{symbol}] skipped after error: {exc}")
            continue

        if not df.empty:
            frames.append(df)
        time.sleep(REQUEST_SLEEP + random.random() * 0.2)

    if not frames:
        raise RuntimeError("No stock data was downloaded")

    panel = deduplicate_market(pd.concat(frames, ignore_index=True))
    panel = attach_membership(panel, universe)

    path = PROCESSED_DIR / (
        f"hs300_dynamic_panel_{date_key(start_date)}_"
        f"{date_key(end_date)}_{DATA_SOURCE}.parquet"
    )
    save_parquet(panel, path)
    print("Panel saved to:", path)
    print("Panel shape:", panel.shape)
    return panel


# =========================================================
# Validation and research sample
# =========================================================

def validate_panel(panel: pd.DataFrame) -> None:
    duplicates = int(panel.duplicated(["ticker", "date"]).sum())
    if duplicates:
        raise ValueError(f"Found {duplicates} duplicated ticker-date rows")

    print("\nValidation summary")
    print("Date range:", panel["date"].min(), "->", panel["date"].max())
    print("Tickers:", panel["ticker"].nunique())
    print("Rows:", len(panel))
    print("Duplicate ticker-date rows:", duplicates)
    print("QFQ close missing rate:", panel["qfq_close"].isna().mean())
    print("Trade status missing rate:", panel["trade_status"].isna().mean())


def make_research_sample(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Membership is enforced here. Suspended/ST observations remain available,
    so execution rules can inspect them instead of losing them during download.
    """
    return panel.loc[panel["is_hs300_member"].eq(True)].copy()


# =========================================================
# Main
# =========================================================

def main() -> None:
    baostock_login()
    try:
        universe = build_hs300_monthly_universe(
            START_DATE,
            END_DATE,
            force_download=False,
        )
        symbols = historical_union_symbols(universe)
        print(f"Historical HS300 union: {len(symbols)} stocks")

        panel = download_stock_panel(
            symbols=symbols,
            start_date=START_DATE,
            end_date=END_DATE,
            universe=universe,
            force_download=False,
        )
        validate_panel(panel)

        research = make_research_sample(panel)
        research_path = PROCESSED_DIR / (
            f"hs300_member_sample_{date_key(START_DATE)}_"
            f"{date_key(END_DATE)}_{DATA_SOURCE}.parquet"
        )
        save_parquet(research, research_path)
        print("Research sample saved to:", research_path)
        print("Research sample shape:", research.shape)

    finally:
        baostock_logout()


if __name__ == "__main__":
    main()
