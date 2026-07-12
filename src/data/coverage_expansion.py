from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.akshare_financials import add_ttm_and_growth, merge_statements, load_statement_directory
from src.data.coarse_industry import build_coarse_industry_panel
from src.data.float_cap_proxy import build_float_cap_proxy_panel

FACTOR_COLUMNS = [
    "bp", "ep", "sp", "cfp", "value_composite_raw", "roe", "gross_profitability",
    "ocf_to_assets", "revenue_growth", "earnings_growth",
]


def load_broad_statements(raw_root, start_date="2014-01-01", end_date="2025-12-31"):
    statements, mappings = {}, []
    for statement_type in ["balance_sheet", "profit_sheet", "cash_flow_sheet"]:
        frame, mapping = load_statement_directory(raw_root, statement_type, start_date, end_date)
        statements[statement_type] = frame
        mappings.extend(mapping)
    merged = add_ttm_and_growth(merge_statements(statements))
    return merged, pd.DataFrame(mappings)


def build_broad_monthly_panel(
    statements: pd.DataFrame,
    dynamic_panel: pd.DataFrame,
    market_caps: pd.DataFrame,
    raw_industry: pd.DataFrame | None = None,
) -> pd.DataFrame:
    market = dynamic_panel.copy()
    # Normalize datetime precision because parquet sources can expose dates as
    # datetime64[us] while pandas' merge_asof requires identical key dtypes.
    market["date"] = pd.to_datetime(market["date"], errors="coerce").astype("datetime64[ns]")
    market["ticker"] = market["ticker"].astype(str).str.zfill(6)
    dates = market.groupby(market["date"].dt.to_period("M"))["date"].max().sort_values()
    monthly = market[market["date"].isin(dates.values)].copy().sort_values(["ticker", "date"])
    monthly = monthly[[c for c in ["date", "ticker", "raw_close", "qfq_close", "is_hs300_member", "trade_status", "is_st"] if c in monthly.columns]]
    statements = statements.copy()
    statements["ticker"] = statements["ticker"].astype(str).str.zfill(6)
    statements["available_date"] = pd.to_datetime(statements["available_date"], errors="coerce").astype("datetime64[ns]")
    statements = statements.sort_values(["ticker", "available_date"])
    parts = []
    for ticker, rows in monthly.groupby("ticker", sort=False):
        f = statements[statements["ticker"].eq(ticker)]
        if f.empty:
            continue
        parts.append(pd.merge_asof(rows.sort_values("date"), f.sort_values("available_date"), left_on="date", right_on="available_date", by="ticker", direction="backward"))
    if not parts:
        raise RuntimeError("No broad financial rows matched the monthly dynamic universe")
    out = pd.concat(parts, ignore_index=True)
    caps = market_caps.copy()
    caps["date"] = pd.to_datetime(caps["date"], errors="coerce").astype("datetime64[ns]")
    caps["ticker"] = caps["ticker"].astype(str).str.zfill(6)
    cap_parts = []
    for ticker, rows in out.groupby("ticker", sort=False):
        c = caps[caps["ticker"].eq(ticker)].sort_values("date")
        if c.empty:
            rows = rows.copy(); rows["market_cap"] = np.nan; rows["float_market_cap"] = np.nan; rows["market_cap_observation_date"] = pd.NaT; rows["market_cap_source"] = "missing"
        else:
            rows = pd.merge_asof(rows.sort_values("date"), c, left_on="date", right_on="date", by="ticker", direction="backward", suffixes=("", "_cap"))
        cap_parts.append(rows)
    out = pd.concat(cap_parts, ignore_index=True)
    industry = build_coarse_industry_panel(out[["date", "ticker"]], raw_industry)
    out = out.merge(industry, on=["date", "ticker"], how="left")
    out = build_float_cap_proxy_panel(out)
    out["equity"] = out["equity_parent"].fillna(out["total_equity"])
    out["profit_ttm"] = out["net_profit_parent_ttm"].fillna(out["net_profit_ttm"])
    positive_cap = out["float_market_cap_used"].where(out["float_market_cap_used"] > 0)
    positive_assets = out["total_assets"].where(out["total_assets"] > 0)
    positive_equity = out["equity"].where(out["equity"] > 0)
    out["bp"] = out["equity"] / positive_cap; out["ep"] = out["profit_ttm"] / positive_cap; out["sp"] = out["revenue_ttm"] / positive_cap; out["cfp"] = out["operating_cash_flow_ttm"] / positive_cap
    out["value_composite_raw"] = out[["bp", "ep", "sp", "cfp"]].mean(axis=1)
    out["roe"] = out["profit_ttm"] / positive_equity; out["gross_profitability"] = out["gross_profit_ttm"] / positive_assets; out["ocf_to_assets"] = out["operating_cash_flow_ttm"] / positive_assets
    out["revenue_growth"] = out["revenue_growth_yoy"]; out["earnings_growth"] = out["earnings_growth_yoy"]
    out["financial_data_quality"] = np.select([out["available_date_method"].eq("reported") & out["financial_data_quality"].isna() if "financial_data_quality" in out else np.zeros(len(out), dtype=bool), out["available_date_method"].eq("conservative_lag")], ["reported", "conservative_lag"], default="mixed_or_unknown")
    out["financial_imputation_flag"] = out["available_date_method"].ne("reported")
    out["source_revision_available"] = False
    out["data_vintage"] = pd.Timestamp.today().normalize()
    out["announcement_date_method"] = out["available_date_method"]
    out["book_equity"] = out["equity"]; out["net_profit"] = out["profit_ttm"]; out["revenue"] = out["revenue_ttm"]; out["gross_profit"] = out["gross_profit_ttm"]; out["operating_cash_flow"] = out["operating_cash_flow_ttm"]
    return out.sort_values(["date", "ticker"]).reset_index(drop=True)
