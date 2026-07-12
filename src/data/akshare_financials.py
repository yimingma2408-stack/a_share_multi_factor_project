from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)

STATEMENT_SPECS = {
    "balance_sheet": {
        "em_func": "stock_balance_sheet_by_report_em",
        "sina_symbol": "资产负债表",
    },
    "profit_sheet": {
        "em_func": "stock_profit_sheet_by_report_em",
        "sina_symbol": "利润表",
    },
    "cash_flow_sheet": {
        "em_func": "stock_cash_flow_sheet_by_report_em",
        "sina_symbol": "现金流量表",
    },
}

FIELD_CANDIDATES = {
    "report_date": ["REPORT_DATE", "报告日期", "报告日", "报表日期", "截止日期", "截止日", "会计期间"],
    "available_date": [
        "NOTICE_DATE",
        "公告日期",
        "公告日",
        "UPDATE_DATE",
        "更新日期",
        "发布日期",
        "披露日期",
    ],
    "revenue": [
        "营业收入",
        "营业总收入",
        "TOTAL_OPERATE_INCOME",
        "OPERATE_INCOME",
        "TOTAL_REVENUE",
        "REVENUE",
    ],
    "operating_cost": ["营业成本", "营业总成本", "OPERATE_COST", "TOTAL_OPERATE_COST"],
    "net_profit": ["净利润", "NETPROFIT", "NET_PROFIT", "TOTAL_PROFIT"],
    "net_profit_parent": [
        "归属于母公司所有者的净利润",
        "归母净利润",
        "PARENT_NETPROFIT",
        "NETPROFIT_PARENT",
    ],
    "total_assets": ["资产总计", "总资产", "TOTAL_ASSETS"],
    "total_equity": ["所有者权益合计", "股东权益合计", "TOTAL_EQUITY"],
    "equity_parent": [
        "归属于母公司股东权益合计",
        "归属于母公司所有者权益合计",
        "TOTAL_PARENT_EQUITY",
        "PARENT_EQUITY",
    ],
    "operating_cash_flow": [
        "经营活动产生的现金流量净额",
        "经营现金流量净额",
        "NETCASH_OPERATE",
        "NETCASH_OPERATENOTE",
        "NET_CASH_FLOWS_OPERATE_ACT",
    ],
}

FLOW_FIELDS = [
    "revenue",
    "operating_cost",
    "net_profit",
    "net_profit_parent",
    "operating_cash_flow",
]
BALANCE_FIELDS = ["total_assets", "total_equity", "equity_parent"]


@dataclass
class FetchResult:
    """Result of fetching one financial statement."""

    status: str
    rows: int
    source: str | None
    error: str
    path: Path | None


def _normalized_label(value: object) -> str:
    return re.sub(r"[\s_\-（）()]+", "", str(value)).upper()


def find_first_existing_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """Return the first matching column using exact and normalized labels."""
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    normalized = {_normalized_label(col): str(col) for col in df.columns}
    for candidate in candidates:
        match = normalized.get(_normalized_label(candidate))
        if match is not None:
            return match
    return None


def normalize_ticker(value: object) -> str:
    """Normalize common A-share ticker representations to six digits."""
    text = str(value).strip().upper()
    match = re.search(r"(\d{6})", text)
    if not match:
        raise ValueError(f"Cannot parse A-share ticker: {value!r}")
    return match.group(1)


def ticker_to_em_symbol(value: object) -> str:
    """Convert a project ticker to the Eastmoney AKShare symbol format."""
    ticker = normalize_ticker(value)
    if ticker.startswith(("4", "8")):
        return f"BJ{ticker}"
    if ticker.startswith(("5", "6", "9")):
        return f"SH{ticker}"
    return f"SZ{ticker}"


def ticker_to_sina_symbol(value: object) -> str:
    """Convert a project ticker to the Sina AKShare symbol format."""
    return ticker_to_em_symbol(value).lower()


def read_universe(project_root: Path) -> list[str]:
    """Read the dynamic HS300 universe, falling back to clean daily data."""
    dynamic = project_root / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"
    clean = project_root / "data/processed/clean_daily_data.csv"
    if dynamic.exists():
        frame = pd.read_parquet(dynamic, columns=["ticker"])
    elif clean.exists():
        frame = pd.read_csv(clean, usecols=["ticker"])
    else:
        raise FileNotFoundError(
            "No stock universe found. Expected the dynamic HS300 parquet or data/processed/clean_daily_data.csv."
        )
    return sorted({normalize_ticker(value) for value in frame["ticker"].dropna()})


def save_frame_with_fallback(df: pd.DataFrame, parquet_path: Path) -> Path:
    """Save parquet when possible and automatically fall back to CSV."""
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(parquet_path, index=False)
        return parquet_path
    except (ImportError, ModuleNotFoundError):
        csv_path = parquet_path.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        LOGGER.warning("Parquet engine unavailable; wrote %s", csv_path)
        return csv_path


def read_cached_frame(path_without_suffix: Path) -> tuple[pd.DataFrame, Path] | None:
    """Read a cached parquet or CSV table."""
    parquet_path = path_without_suffix.with_suffix(".parquet")
    csv_path = path_without_suffix.with_suffix(".csv")
    if parquet_path.exists():
        return pd.read_parquet(parquet_path), parquet_path
    if csv_path.exists():
        return pd.read_csv(csv_path), csv_path
    return None


def _import_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("AKShare is required. Install it with: pip install akshare") from exc
    return ak


def _call_with_retries(
    call: Callable[[], pd.DataFrame],
    description: str,
    retries: int,
    sleep_min: float,
    sleep_max: float,
) -> pd.DataFrame:
    errors = []
    for attempt in range(1, retries + 1):
        try:
            frame = call()
            if frame is None or frame.empty:
                raise RuntimeError("empty response")
            return frame
        except Exception as exc:  # Network providers raise many exception types.
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            LOGGER.warning("%s failed (%s/%s): %s", description, attempt, retries, exc)
            if attempt < retries:
                time.sleep(random.uniform(sleep_min, sleep_max))
        finally:
            time.sleep(random.uniform(sleep_min, sleep_max))
    raise RuntimeError(" | ".join(errors))


def fetch_statement(
    ticker: str,
    statement_type: str,
    output_root: Path,
    start_date: str | pd.Timestamp = "2014-01-01",
    end_date: str | pd.Timestamp = "2025-12-31",
    force: bool = False,
    retries: int = 3,
    sleep_min: float = 0.5,
    sleep_max: float = 2.0,
) -> FetchResult:
    """Fetch one statement from Eastmoney, falling back to Sina."""
    if statement_type not in STATEMENT_SPECS:
        raise ValueError(f"Unsupported statement type: {statement_type}")
    symbol = ticker_to_em_symbol(ticker)
    base = output_root / statement_type / f"{symbol}_{statement_type}"
    cached = read_cached_frame(base)
    if cached is not None and not force:
        frame, path = cached
        source = str(frame["_akshare_source"].iloc[0]) if "_akshare_source" in frame and len(frame) else "cached"
        return FetchResult("cached", len(frame), source, "", path)

    ak = _import_akshare()
    spec = STATEMENT_SPECS[statement_type]
    errors = []
    providers = [
        (
            "eastmoney",
            lambda: getattr(ak, spec["em_func"])(symbol=symbol),
        ),
        (
            "sina",
            lambda: ak.stock_financial_report_sina(
                stock=ticker_to_sina_symbol(ticker),
                symbol=spec["sina_symbol"],
            ),
        ),
    ]
    for source, call in providers:
        try:
            frame = _call_with_retries(
                call,
                f"{symbol} {statement_type} {source}",
                retries,
                sleep_min,
                sleep_max,
            ).copy()
            report_col = find_first_existing_column(frame, FIELD_CANDIDATES["report_date"])
            if report_col is not None:
                report_dates = pd.to_datetime(frame[report_col], errors="coerce")
                frame = frame[report_dates.between(pd.Timestamp(start_date), pd.Timestamp(end_date))].copy()
                if frame.empty:
                    raise RuntimeError(f"no rows in requested range {start_date} to {end_date}")
            frame["_akshare_source"] = source
            frame["_requested_ticker"] = normalize_ticker(ticker)
            path = save_frame_with_fallback(frame, base.with_suffix(".parquet"))
            schema_path = base.with_name(f"{base.name}_columns.json")
            schema_path.write_text(
                json.dumps([str(col) for col in frame.columns], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return FetchResult("success", len(frame), source, "", path)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    return FetchResult("failed", 0, None, " || ".join(errors), None)


def conservative_available_date(report_date: pd.Series) -> pd.Series:
    """Apply conservative statutory lags when no disclosure date is available."""
    dates = pd.to_datetime(report_date, errors="coerce")
    lags = dates.dt.month.map({3: 45, 6: 75, 9: 45, 12: 120}).fillna(120)
    return dates + pd.to_timedelta(lags, unit="D")


def _reshape_sina_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """Reshape common Sina item-by-row output into report-date rows."""
    if find_first_existing_column(df, FIELD_CANDIDATES["report_date"]) is not None:
        return df
    date_columns = [col for col in df.columns if pd.notna(pd.to_datetime(str(col), errors="coerce"))]
    if not date_columns or df.empty:
        return df
    item_col = next((col for col in df.columns if col not in date_columns), df.columns[0])
    transposed = df.set_index(item_col)[date_columns].T.reset_index().rename(columns={"index": "REPORT_DATE"})
    return transposed


def normalize_statement(
    df: pd.DataFrame,
    ticker: str,
    statement_type: str,
    start_date: str | pd.Timestamp = "2014-01-01",
    end_date: str | pd.Timestamp = "2025-12-31",
) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Map an AKShare statement to stable English fields and PIT dates."""
    source = (
        str(df["_akshare_source"].dropna().iloc[0])
        if "_akshare_source" in df.columns and df["_akshare_source"].notna().any()
        else "unknown"
    )
    work = _reshape_sina_if_needed(df.copy())
    mapping = {target: find_first_existing_column(work, candidates) for target, candidates in FIELD_CANDIDATES.items()}
    report_col = mapping["report_date"]
    if report_col is None:
        raise ValueError(f"{ticker} {statement_type}: no report-date column found")

    out = pd.DataFrame(index=work.index)
    out["ticker"] = normalize_ticker(ticker)
    out["report_date"] = pd.to_datetime(work[report_col], errors="coerce").dt.normalize()
    available_col = mapping["available_date"]
    real_available = pd.to_datetime(work[available_col], errors="coerce").dt.normalize() if available_col else pd.Series(pd.NaT, index=work.index)
    fallback = conservative_available_date(out["report_date"])
    out["available_date"] = real_available.fillna(fallback)
    out["available_date_method"] = np.where(real_available.notna(), "reported", "conservative_lag")
    out["statement_type"] = statement_type
    out["source"] = source

    for field in FLOW_FIELDS + BALANCE_FIELDS:
        column = mapping[field]
        out[field] = pd.to_numeric(work[column], errors="coerce") if column else np.nan
    out["gross_profit"] = out["revenue"] - out["operating_cost"]
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    out = out[out["report_date"].between(start, end)].dropna(subset=["report_date", "available_date"])
    out = (
        out.sort_values(["report_date", "available_date"])
        .drop_duplicates(["ticker", "report_date"], keep="last")
        .reset_index(drop=True)
    )
    return out, mapping


def load_statement_directory(
    raw_root: Path,
    statement_type: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Load and normalize all cached files for one statement type."""
    folder = raw_root / statement_type
    files = sorted(list(folder.glob(f"*_{statement_type}.parquet")) + list(folder.glob(f"*_{statement_type}.csv")))
    frames = []
    mapping_rows = []
    for path in files:
        try:
            raw = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
            ticker = normalize_ticker(path.name)
            normalized, mapping = normalize_statement(raw, ticker, statement_type, start_date, end_date)
            frames.append(normalized)
            for target, source_column in mapping.items():
                mapping_rows.append(
                    {
                        "statement_type": statement_type,
                        "ticker": ticker,
                        "target_field": target,
                        "source_column": source_column,
                    }
                )
        except Exception as exc:
            LOGGER.error("Failed to normalize %s: %s", path, exc)
            mapping_rows.append(
                {
                    "statement_type": statement_type,
                    "ticker": path.stem[:8],
                    "target_field": "__file_error__",
                    "source_column": f"{type(exc).__name__}: {exc}",
                }
            )
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, mapping_rows


def _select_statement_columns(frame: pd.DataFrame, statement_type: str) -> pd.DataFrame:
    base = ["ticker", "report_date", "available_date", "available_date_method", "source"]
    if statement_type == "profit_sheet":
        fields = ["revenue", "operating_cost", "gross_profit", "net_profit", "net_profit_parent"]
    elif statement_type == "balance_sheet":
        fields = BALANCE_FIELDS
    else:
        fields = ["operating_cash_flow"]
    selected = frame[base + fields].copy()
    suffix = statement_type.replace("_sheet", "")
    return selected.rename(
        columns={
            "available_date": f"available_date_{suffix}",
            "available_date_method": f"available_date_method_{suffix}",
            "source": f"source_{suffix}",
        }
    )


def merge_statements(statements: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Conservatively merge three statements by ticker and report period."""
    merged: pd.DataFrame | None = None
    for statement_type in ["profit_sheet", "balance_sheet", "cash_flow_sheet"]:
        frame = statements.get(statement_type, pd.DataFrame())
        if frame.empty:
            continue
        selected = _select_statement_columns(frame, statement_type)
        merged = selected if merged is None else merged.merge(selected, on=["ticker", "report_date"], how="outer")
    if merged is None or merged.empty:
        raise RuntimeError("No normalized financial statement rows are available")

    available_cols = [
        col for col in merged if col.startswith("available_date_") and not col.startswith("available_date_method_")
    ]
    method_cols = [col for col in merged if col.startswith("available_date_method_")]
    merged["available_date"] = merged[available_cols].max(axis=1)
    merged["available_date_method"] = merged[method_cols].apply(
        lambda row: "reported" if row.dropna().eq("reported").all() and len(row.dropna()) else (
            "conservative_lag" if row.dropna().eq("conservative_lag").all() and len(row.dropna()) else "mixed"
        ),
        axis=1,
    )
    for field in FLOW_FIELDS + BALANCE_FIELDS + ["gross_profit"]:
        if field not in merged:
            merged[field] = np.nan
    return merged.sort_values(["ticker", "report_date", "available_date"]).reset_index(drop=True)


def _quarter_ordinals(dates: pd.Series) -> np.ndarray:
    periods = pd.PeriodIndex(pd.to_datetime(dates), freq="Q-DEC")
    return np.asarray([period.ordinal for period in periods], dtype=int)


def add_ttm_and_growth(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert cumulative YTD flows to single quarters, TTM values, and YoY growth."""
    outputs = []
    for _, group in frame.groupby("ticker", sort=False):
        g = group.sort_values("report_date").drop_duplicates("report_date", keep="last").copy()
        ordinals = _quarter_ordinals(g["report_date"])
        years = g["report_date"].dt.year.to_numpy()
        quarters = g["report_date"].dt.quarter.to_numpy()
        for field in FLOW_FIELDS + ["gross_profit"]:
            cumulative = pd.to_numeric(g[field], errors="coerce")
            single = pd.Series(np.nan, index=g.index, dtype=float)
            for position, index in enumerate(g.index):
                current = cumulative.loc[index]
                if pd.isna(current):
                    continue
                if quarters[position] == 1:
                    single.loc[index] = current
                elif position > 0 and years[position - 1] == years[position] and quarters[position - 1] == quarters[position] - 1:
                    previous = cumulative.iloc[position - 1]
                    if pd.notna(previous):
                        single.loc[index] = current - previous
            g[f"{field}_quarter"] = single
            values = single.to_numpy(dtype=float)
            ttm = np.full(len(g), np.nan)
            for position in range(3, len(g)):
                if ordinals[position] - ordinals[position - 3] == 3 and np.isfinite(values[position - 3 : position + 1]).all():
                    ttm[position] = values[position - 3 : position + 1].sum()
            g[f"{field}_ttm"] = ttm

        revenue_lag = g["revenue_ttm"].shift(4)
        earnings_lag = g["net_profit_ttm"].shift(4)
        exact_lag = pd.Series(ordinals, index=g.index) - pd.Series(ordinals, index=g.index).shift(4) == 4
        g["revenue_growth_yoy"] = (g["revenue_ttm"] / revenue_lag - 1.0).where(exact_lag & revenue_lag.ne(0))
        g["earnings_growth_yoy"] = (
            g["net_profit_ttm"] / earnings_lag.abs() - 1.0
        ).where(exact_lag & earnings_lag.abs().ge(1e-6))
        outputs.append(g)
    return pd.concat(outputs, ignore_index=True) if outputs else frame.copy()


def load_trade_panel(project_root: Path) -> pd.DataFrame:
    """Load project trade dates and tickers for point-in-time as-of merging."""
    dynamic = project_root / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"
    clean = project_root / "data/processed/clean_daily_data.csv"
    if dynamic.exists():
        columns = ["date", "ticker"]
        schema = pd.read_parquet(dynamic).columns
        for optional in ["is_hs300_member", "raw_close", "close"]:
            if optional in schema:
                columns.append(optional)
        panel = pd.read_parquet(dynamic, columns=columns)
    elif clean.exists():
        panel = pd.read_csv(clean)
    else:
        raise FileNotFoundError("No daily market panel is available for point-in-time merging")
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["ticker"] = panel["ticker"].map(normalize_ticker)
    return panel.dropna(subset=["date", "ticker"]).sort_values(["ticker", "date"])


def _load_market_cap_panel(project_root: Path) -> tuple[pd.DataFrame, str]:
    candidates = [
        project_root / "data/processed/industry_size_panel.parquet",
        project_root / "data/processed/clean_daily_data.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        market_col = find_first_existing_column(frame, ["market_cap", "total_mv", "总市值"])
        if market_col and {"date", "ticker"}.issubset(frame.columns):
            out = frame[["date", "ticker", market_col]].rename(columns={market_col: "market_cap"}).copy()
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out["ticker"] = out["ticker"].map(normalize_ticker)
            out["market_cap"] = pd.to_numeric(out["market_cap"], errors="coerce")
            return out.dropna(subset=["date", "ticker"]).sort_values(["ticker", "date"]), str(path.relative_to(project_root))
    return pd.DataFrame(columns=["date", "ticker", "market_cap"]), "unavailable"


def build_point_in_time_panel(statements: pd.DataFrame, project_root: Path) -> tuple[pd.DataFrame, str]:
    """As-of merge only statements available on or before each trade date."""
    market = load_trade_panel(project_root)
    market_cap, market_cap_source = _load_market_cap_panel(project_root)
    parts = []
    statement_columns = [col for col in statements.columns if col not in {"ticker"}]
    for ticker, trade_rows in market.groupby("ticker", sort=False):
        financials = statements[statements["ticker"].eq(ticker)]
        if financials.empty:
            continue
        matched = pd.merge_asof(
            trade_rows.sort_values("date"),
            financials[["ticker"] + statement_columns].sort_values("available_date"),
            left_on="date",
            right_on="available_date",
            by="ticker",
            direction="backward",
            allow_exact_matches=True,
        )
        parts.append(matched)
    if not parts:
        raise RuntimeError("No point-in-time statement rows matched the project trade panel")
    panel = pd.concat(parts, ignore_index=True)

    if not market_cap.empty:
        cap_parts = []
        for ticker, rows in panel.groupby("ticker", sort=False):
            caps = market_cap[market_cap["ticker"].eq(ticker)]
            if caps.empty:
                rows = rows.copy()
                rows["market_cap"] = np.nan
            else:
                rows = pd.merge_asof(
                    rows.sort_values("date"),
                    caps.sort_values("date").rename(columns={"date": "market_cap_date"}),
                    left_on="date",
                    right_on="market_cap_date",
                    by="ticker",
                    direction="backward",
                )
            cap_parts.append(rows)
        panel = pd.concat(cap_parts, ignore_index=True)
    else:
        panel["market_cap"] = np.nan

    panel["equity"] = panel["equity_parent"].fillna(panel["total_equity"])
    panel["profit_ttm"] = panel["net_profit_parent_ttm"].fillna(panel["net_profit_ttm"])
    positive_cap = panel["market_cap"].where(panel["market_cap"] > 0)
    positive_assets = panel["total_assets"].where(panel["total_assets"] > 0)
    positive_equity = panel["equity"].where(panel["equity"] > 0)
    panel["bp"] = panel["equity"] / positive_cap
    panel["ep"] = panel["profit_ttm"] / positive_cap
    panel["sp"] = panel["revenue_ttm"] / positive_cap
    panel["cfp"] = panel["operating_cash_flow_ttm"] / positive_cap
    panel["value_composite_raw"] = panel[["bp", "ep", "sp", "cfp"]].mean(axis=1)
    panel["roe"] = panel["profit_ttm"] / positive_equity
    panel["gross_profitability"] = panel["gross_profit_ttm"] / positive_assets
    panel["ocf_to_assets"] = panel["operating_cash_flow_ttm"] / positive_assets
    panel["revenue_growth"] = panel["revenue_growth_yoy"]
    panel["earnings_growth"] = panel["earnings_growth_yoy"]

    # Lightweight aliases keep the new panel compatible with existing factor builders.
    panel["announcement_date"] = panel["available_date"]
    panel["book_equity"] = panel["equity"]
    panel["net_profit"] = panel["profit_ttm"]
    panel["revenue"] = panel["revenue_ttm"]
    panel["gross_profit"] = panel["gross_profit_ttm"]
    panel["operating_cash_flow"] = panel["operating_cash_flow_ttm"]
    core = [
        "date",
        "ticker",
        "report_date",
        "available_date",
        "available_date_method",
        "revenue_ttm",
        "operating_cost_ttm",
        "gross_profit_ttm",
        "net_profit_ttm",
        "net_profit_parent_ttm",
        "operating_cash_flow_ttm",
        "total_assets",
        "total_equity",
        "equity_parent",
        "market_cap",
        "bp",
        "ep",
        "sp",
        "cfp",
        "value_composite_raw",
        "roe",
        "gross_profitability",
        "ocf_to_assets",
        "revenue_growth",
        "earnings_growth",
        "announcement_date",
        "book_equity",
        "net_profit",
        "revenue",
        "gross_profit",
        "operating_cash_flow",
    ]
    optional = [col for col in ["is_hs300_member", "raw_close", "close"] if col in panel]
    return panel[core + optional].sort_values(["date", "ticker"]).reset_index(drop=True), market_cap_source
