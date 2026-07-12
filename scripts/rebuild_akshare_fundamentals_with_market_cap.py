from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FUNDAMENTAL_PATH = ROOT / "data/processed/fundamental_panel_akshare.parquet"
MARKET_CAP_PATH = ROOT / "data/processed/market_cap_panel.parquet"
SAFE_OUTPUT_PATH = ROOT / "data/processed/fundamental_panel_akshare_with_market_cap.parquet"


def winsorized_zscore(series: pd.Series) -> pd.Series:
    """Winsorize at 1%/99% and standardize one date's cross-section."""
    values = pd.to_numeric(series, errors="coerce")
    valid = values.dropna()
    if len(valid) < 2:
        return pd.Series(np.nan, index=series.index)
    lower, upper = valid.quantile([0.01, 0.99])
    clipped = values.clip(lower, upper)
    standard_deviation = clipped.std(ddof=0)
    if not np.isfinite(standard_deviation) or standard_deviation <= 1e-12:
        return pd.Series(np.nan, index=series.index)
    return (clipped - clipped.mean()) / standard_deviation


def merge_market_cap_backward(fundamentals: pd.DataFrame, market_caps: pd.DataFrame) -> pd.DataFrame:
    """Attach only same-day or earlier market-cap observations by ticker."""
    fundamentals = fundamentals.copy()
    fundamentals["date"] = pd.to_datetime(fundamentals["date"], errors="coerce").astype("datetime64[ns]")
    fundamentals["ticker"] = fundamentals["ticker"].astype(str).str.zfill(6)
    fundamentals = fundamentals.drop(
        columns=["market_cap", "float_market_cap", "market_cap_source", "market_cap_observation_date"],
        errors="ignore",
    )
    market_caps = market_caps.copy()
    market_caps["date"] = pd.to_datetime(market_caps["date"], errors="coerce").astype("datetime64[ns]")
    market_caps["ticker"] = market_caps["ticker"].astype(str).str.zfill(6)
    cap_columns = ["ticker", "date", "market_cap", "float_market_cap", "market_cap_source"]
    if "market_cap_observation_date" in market_caps:
        cap_columns.append("market_cap_observation_date")
    parts = []
    for ticker, rows in fundamentals.groupby("ticker", sort=False):
        caps = market_caps[market_caps["ticker"].eq(ticker)][cap_columns].sort_values("date")
        if caps.empty:
            missing = rows.copy()
            missing["market_cap"] = np.nan
            missing["float_market_cap"] = np.nan
            missing["market_cap_source"] = np.nan
            missing["market_cap_observation_date"] = pd.NaT
            parts.append(missing)
            continue
        rows = rows.copy()
        rows["date"] = pd.to_datetime(rows["date"], errors="coerce").astype("datetime64[ns]")
        caps = caps.rename(columns={"date": "cap_panel_date"})
        caps["cap_panel_date"] = pd.to_datetime(caps["cap_panel_date"], errors="coerce").astype("datetime64[ns]")
        matched = pd.merge_asof(
            rows.sort_values("date"),
            caps.sort_values("cap_panel_date"),
            left_on="date",
            right_on="cap_panel_date",
            by="ticker",
            direction="backward",
        )
        if "market_cap_observation_date" not in matched:
            matched["market_cap_observation_date"] = matched["cap_panel_date"]
        parts.append(matched)
    return pd.concat(parts, ignore_index=True).sort_values(["date", "ticker"]).reset_index(drop=True)


def numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric column or an all-missing series when the input schema lacks it."""
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def recalculate_factors(panel: pd.DataFrame) -> pd.DataFrame:
    """Recalculate value, quality, and growth factors with valid denominators."""
    out = panel.copy()
    market_cap = pd.to_numeric(out["market_cap"], errors="coerce").where(lambda values: values > 0)
    equity = pd.to_numeric(out["equity_parent"], errors="coerce").fillna(
        pd.to_numeric(out["total_equity"], errors="coerce")
    )
    profit = pd.to_numeric(out["net_profit_parent_ttm"], errors="coerce").fillna(
        pd.to_numeric(out["net_profit_ttm"], errors="coerce")
    )
    assets = pd.to_numeric(out["total_assets"], errors="coerce").where(lambda values: values > 0)
    out["bp"] = equity / market_cap
    out["ep"] = profit / market_cap
    out["sp"] = pd.to_numeric(out["revenue_ttm"], errors="coerce") / market_cap
    out["cfp"] = pd.to_numeric(out["operating_cash_flow_ttm"], errors="coerce") / market_cap
    out["roe"] = profit / equity.where(equity > 0)
    out["gross_profitability"] = pd.to_numeric(out["gross_profit_ttm"], errors="coerce") / assets
    out["ocf_to_assets"] = pd.to_numeric(out["operating_cash_flow_ttm"], errors="coerce") / assets
    out["revenue_growth"] = numeric_column(out, "revenue_growth_yoy").fillna(numeric_column(out, "revenue_growth"))
    out["earnings_growth"] = numeric_column(out, "earnings_growth_yoy").fillna(numeric_column(out, "earnings_growth"))
    component_z = []
    for factor in ["bp", "ep", "sp", "cfp"]:
        column = f"{factor}_value_z"
        out[column] = out.groupby("date")[factor].transform(winsorized_zscore)
        component_z.append(column)
    out["value_composite_raw"] = out[component_z].mean(axis=1, skipna=True).where(
        out[component_z].notna().any(axis=1)
    )
    return out


def main() -> None:
    """Merge daily caps, enforce PIT constraints, recalculate factors, and save safely."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not FUNDAMENTAL_PATH.exists():
        raise FileNotFoundError(f"Missing AKShare fundamental panel: {FUNDAMENTAL_PATH}")
    if not MARKET_CAP_PATH.exists():
        raise FileNotFoundError(f"Missing market-cap panel: {MARKET_CAP_PATH}")
    fundamentals = pd.read_parquet(FUNDAMENTAL_PATH)
    market_caps = pd.read_parquet(MARKET_CAP_PATH)
    result = recalculate_factors(merge_market_cap_backward(fundamentals, market_caps))
    financial_violations = int(
        (pd.to_datetime(result["available_date"], errors="coerce") > pd.to_datetime(result["date"], errors="coerce")).sum()
    )
    cap_violations = int(
        (
            pd.to_datetime(result["market_cap_observation_date"], errors="coerce")
            > pd.to_datetime(result["date"], errors="coerce")
        ).sum()
    )
    if financial_violations or cap_violations:
        raise RuntimeError(
            f"Point-in-time violation detected: financial={financial_violations}, market_cap={cap_violations}"
        )
    result.to_parquet(SAFE_OUTPUT_PATH, index=False)
    result.to_parquet(FUNDAMENTAL_PATH, index=False)
    logging.info("Wrote %s and refreshed %s (%s rows)", SAFE_OUTPUT_PATH, FUNDAMENTAL_PATH, len(result))


if __name__ == "__main__":
    main()
