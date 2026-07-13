from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.correlations import factor_correlation, factor_correlation_by_year
from src.analysis.fama_macbeth import run_fama_macbeth
from src.analysis.grouping import quantile_group_returns
from src.analysis.ic import compute_rank_ic, summarize_ic
from src.factors.preprocess import neutralize_cross_section, preprocess_by_date
from src.factors.value import build_value_factors

PROCESSED_DIR = ROOT / "data/processed"
REPORT_DIR = ROOT / "reports/final"
MONTHLY_PANEL_PATH = PROCESSED_DIR / "hs300_dynamic_panel_20160101_20251231_baostock.parquet"
FUNDAMENTAL_PATH = PROCESSED_DIR / "fundamental_panel.parquet"
INDUSTRY_SIZE_PATH = PROCESSED_DIR / "industry_size_panel.parquet"


def to_markdown_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "No rows generated."
    display = df.head(max_rows).copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{x:.6g}")
        else:
            display[col] = display[col].astype(str)
    header = "| " + " | ".join(display.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in display.to_numpy(dtype=str)]
    suffix = "\n\n_Table truncated._" if len(df) > max_rows else ""
    return "\n".join([header, sep, *rows]) + suffix


def read_monthly_returns() -> pd.DataFrame:
    panel = pd.read_parquet(MONTHLY_PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    panel["ticker"] = panel["ticker"].astype(str).str.zfill(6)
    month_ends = panel.groupby(panel["date"].dt.to_period("M"))["date"].max().sort_values()
    monthly = panel[panel["date"].isin(month_ends.values)].sort_values(["ticker", "date"]).copy()
    price_col = "qfq_close" if "qfq_close" in monthly.columns else "raw_close"
    monthly["next_price"] = monthly.groupby("ticker")[price_col].shift(-1)
    monthly["fwd_ret_1m"] = monthly["next_price"] / monthly[price_col] - 1.0
    return monthly[["date", "ticker", price_col, "fwd_ret_1m"]].rename(columns={price_col: "price"})


def add_neutralized_factors(df: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    variants = {
        "size": {"size_col": "market_cap", "industry_col": None},
        "industry": {"size_col": None, "industry_col": "industry"},
        "industry_size": {"size_col": "market_cap", "industry_col": "industry"},
    }
    for factor in factor_cols:
        for suffix, kwargs in variants.items():
            col = f"{factor}_{suffix}_neutral"
            out[col] = np.nan
            for _, idx in out.groupby("date").groups.items():
                group = out.loc[idx]
                out.loc[idx, col] = neutralize_cross_section(group, factor, **kwargs)
    return out


def factor_descriptive_stats(df: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    rows = []
    for factor in factor_cols:
        x = pd.to_numeric(df[factor], errors="coerce")
        autocorr = (
            df[["ticker", "date", factor]]
            .sort_values(["ticker", "date"])
            .groupby("ticker")[factor]
            .apply(lambda s: s.autocorr(lag=1))
            .mean()
        )
        rows.append(
            {
                "factor_name": factor,
                "mean": x.mean(),
                "std": x.std(ddof=1),
                "median": x.median(),
                "p05": x.quantile(0.05),
                "p95": x.quantile(0.95),
                "missing_rate": x.isna().mean(),
                "skew": x.skew(),
                "kurtosis": x.kurtosis(),
                "mean_ticker_autocorr_lag1": autocorr,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-tickers", type=int, default=200)
    parser.add_argument("--groups", type=int, default=5)
    args = parser.parse_args()

    fundamentals = pd.read_parquet(FUNDAMENTAL_PATH)
    industry_size = pd.read_parquet(INDUSTRY_SIZE_PATH)
    for frame in (fundamentals, industry_size):
        frame["date"] = pd.to_datetime(frame["date"])
        frame["ticker"] = frame["ticker"].astype(str).str.zfill(6)

    usable = fundamentals.dropna(subset=["market_cap", "book_equity", "net_profit", "revenue", "operating_cash_flow"])
    usable_tickers = usable["ticker"].nunique()
    if usable_tickers < args.min_tickers:
        raise RuntimeError(
            f"Point-in-time fundamental coverage is too small: {usable_tickers} usable tickers; "
            f"need at least {args.min_tickers}. Run scripts/data/acquisition/download_fundamentals_akshare.py first."
        )

    values = build_value_factors(fundamentals)
    values = values.merge(
        industry_size[["date", "ticker", "industry"]].drop_duplicates(["date", "ticker"]),
        on=["date", "ticker"],
        how="left",
    )
    returns = read_monthly_returns()
    panel = values.merge(returns[["date", "ticker", "fwd_ret_1m"]], on=["date", "ticker"], how="left")

    raw_factors = ["bp", "ep", "sp", "cfp", "value_composite_raw"]
    panel = add_neutralized_factors(panel, raw_factors)
    neutral_factors = [f"{factor}_{suffix}_neutral" for factor in raw_factors for suffix in ["size", "industry", "industry_size"]]
    all_factor_inputs = raw_factors + neutral_factors
    panel = preprocess_by_date(panel, all_factor_inputs)
    z_factors = [f"{factor}_z" for factor in all_factor_inputs]

    ic = compute_rank_ic(panel, z_factors, "fwd_ret_1m", min_obs=30)
    ic_summary = summarize_ic(ic).sort_values("mean_rank_ic", ascending=False)
    grouped = pd.concat(
        [quantile_group_returns(panel, factor, "fwd_ret_1m", groups=args.groups, min_obs=30) for factor in z_factors],
        ignore_index=True,
    )
    group_summary = (
        grouped.groupby("factor_name")["long_short_return"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(columns={"mean": "mean_long_short_return", "std": "std_long_short_return", "count": "observations"})
    )
    corr = factor_correlation(panel.dropna(how="all", subset=z_factors), z_factors, method="spearman")
    corr_by_year = factor_correlation_by_year(panel.dropna(how="all", subset=z_factors), z_factors, method="spearman")
    fmb_betas, fmb_summary = run_fama_macbeth(panel, [f"{factor}_z" for factor in raw_factors], "fwd_ret_1m")
    desc = factor_descriptive_stats(panel, z_factors)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PROCESSED_DIR / "value_neutralized_factor_panel.parquet", index=False)
    ic.to_csv(REPORT_DIR / "value_rank_ic.csv", index=False)
    ic_summary.to_csv(REPORT_DIR / "value_rank_ic_summary.csv", index=False)
    grouped.to_csv(REPORT_DIR / "value_group_returns.csv", index=False)
    group_summary.to_csv(REPORT_DIR / "value_group_summary.csv", index=False)
    corr.to_csv(REPORT_DIR / "value_factor_correlation.csv")
    corr_by_year.to_csv(REPORT_DIR / "value_factor_correlation_by_year.csv", index=False)
    fmb_betas.to_csv(REPORT_DIR / "value_fama_macbeth_betas.csv", index=False)
    fmb_summary.to_csv(REPORT_DIR / "value_fama_macbeth_summary.csv", index=False)
    desc.to_csv(REPORT_DIR / "value_factor_descriptive_stats.csv", index=False)

    lines = [
        "# Value and Neutralized Factor Research",
        "",
        "- Universe: dynamic HS300 monthly observations",
        f"- Fundamental rows: {len(fundamentals)}",
        f"- Fundamental tickers: {fundamentals['ticker'].nunique()}",
        f"- Usable tickers with market cap, book equity, net profit, revenue, and cash flow: {usable_tickers}",
        f"- Research rows after return merge: {len(panel)}",
        f"- Date range: {panel['date'].min().date()} to {panel['date'].max().date()}",
        "",
        "## Rank IC Summary",
        "",
        to_markdown_table(ic_summary),
        "",
        "## Grouped Long-Short Summary",
        "",
        to_markdown_table(group_summary.sort_values("mean_long_short_return", ascending=False)),
        "",
        "## Fama-MacBeth Summary",
        "",
        to_markdown_table(fmb_summary),
        "",
        "## Descriptive Statistics",
        "",
        to_markdown_table(desc),
        "",
        "## Method Notes",
        "",
        "- BP, EP, SP, and CFP use `announcement_date` aligned point-in-time financial data.",
        "- Forward returns use next monthly adjusted close from the dynamic HS300 panel.",
        "- Neutralized variants compare size-only, industry-only, and industry plus size residual factors.",
    ]
    report_path = REPORT_DIR / "value_neutralized_factor_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
