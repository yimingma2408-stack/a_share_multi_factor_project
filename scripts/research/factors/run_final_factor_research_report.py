from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.attribution import industry_weight_exposure, market_model_regression, portfolio_exposure
from src.analysis.ic import compute_rank_ic, summarize_ic
from src.backtest.costs import apply_linear_costs, turnover_from_weights
from src.backtest.execution import add_tradable_flags, constrain_rebalance_orders, estimate_execution_costs
from src.evaluation.metrics import performance_summary

PROCESSED = ROOT / "data/processed"
REPORT_DIR = ROOT / "reports/final"


def to_markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
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


def read_monthly_benchmark() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = pd.read_parquet(PROCESSED / "hs300_dynamic_panel_20160101_20251231_baostock.parquet")
    daily["date"] = pd.to_datetime(daily["date"])
    daily["ticker"] = daily["ticker"].astype(str).str.zfill(6)
    month_end_dates = daily.groupby(daily["date"].dt.to_period("M"))["date"].max().sort_values()
    monthly = daily[daily["date"].isin(month_end_dates.values)].sort_values(["ticker", "date"]).copy()
    monthly["next_price"] = monthly.groupby("ticker")["qfq_close"].shift(-1)
    monthly["fwd_ret_1m"] = monthly["next_price"] / monthly["qfq_close"] - 1.0
    benchmark = monthly.groupby("date")["fwd_ret_1m"].mean().rename("benchmark_return").reset_index()
    monthly["month"] = monthly["date"].dt.to_period("M")
    adv = (
        daily.assign(month=daily["date"].dt.to_period("M"))
        .groupby(["month", "ticker"])["amount"]
        .mean()
        .rename("adv")
        .reset_index()
    )
    monthly = monthly.merge(adv, on=["month", "ticker"], how="left")
    return benchmark, monthly


def build_value_strategy(panel: pd.DataFrame, factor_col: str, quantile: float = 0.8) -> pd.DataFrame:
    rows = []
    for date, group in panel.groupby("date", sort=True):
        valid = group[[factor_col, "ticker", "fwd_ret_1m"]].dropna()
        if len(valid) < 50:
            continue
        cutoff = valid[factor_col].quantile(quantile)
        selected = valid[valid[factor_col] >= cutoff].copy()
        if selected.empty:
            continue
        selected["weight"] = 1.0 / len(selected)
        selected["date"] = date
        rows.append(selected[["date", "ticker", "weight", factor_col, "fwd_ret_1m"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def summarize_subperiods(returns: pd.DataFrame) -> pd.DataFrame:
    periods = [
        ("2016-2019", "2016-01-01", "2019-12-31"),
        ("2020-2022", "2020-01-01", "2022-12-31"),
        ("2023-2025", "2023-01-01", "2025-12-31"),
        ("sample_out_2023_2025", "2023-01-01", "2025-12-31"),
    ]
    rows = []
    for name, start, end in periods:
        sub = returns[(returns["date"] >= start) & (returns["date"] <= end)]
        if sub.empty:
            continue
        metrics = performance_summary(sub["portfolio_return"])
        bench = performance_summary(sub["benchmark_return"])
        rows.append(
            {
                "subperiod": name,
                "portfolio_annual_return": metrics.get("annual_return", np.nan),
                "portfolio_sharpe": metrics.get("sharpe", np.nan),
                "portfolio_max_drawdown": metrics.get("max_drawdown", np.nan),
                "benchmark_annual_return": bench.get("annual_return", np.nan),
                "excess_mean_monthly": (sub["portfolio_return"] - sub["benchmark_return"]).mean(),
                "observations": len(sub),
            }
        )
    return pd.DataFrame(rows)


def compute_execution_stress(holdings: pd.DataFrame, monthly_market: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(holdings["date"].unique())
    constrained_rows = []
    prev = pd.DataFrame(columns=["date", "ticker", "weight"])
    for date in dates:
        target = holdings[holdings["date"].eq(date)][["date", "ticker", "weight"]]
        current = prev.assign(date=date) if not prev.empty else prev
        market = monthly_market[monthly_market["date"].eq(date)].copy()
        market = add_tradable_flags(market, trade_status_col="trade_status", st_col="is_st", pct_change_col="pct_change_pct")
        constrained = constrain_rebalance_orders(
            target,
            current_weights=current[["date", "ticker", "weight"]] if not current.empty else None,
            tradability=market[["date", "ticker", "can_buy", "can_sell", "can_hold"]],
        )
        constrained_rows.append(constrained)
        prev = constrained[["date", "ticker", "executed_weight"]].rename(columns={"executed_weight": "weight"})
    constrained_all = pd.concat(constrained_rows, ignore_index=True)

    weights = holdings[["date", "ticker", "weight"]].copy()
    turnover = turnover_from_weights(weights)
    aum = 100_000_000.0
    prev_weights = pd.Series(dtype=float)
    trade_rows = []
    for date, group in weights.sort_values("date").groupby("date", sort=True):
        cur = group.set_index("ticker")["weight"].astype(float)
        aligned = pd.concat([prev_weights.rename("prev"), cur.rename("cur")], axis=1).fillna(0.0)
        trades = aligned.assign(date=date, ticker=aligned.index)
        trades["trade_value"] = (trades["cur"] - trades["prev"]).abs() * aum
        trade_rows.append(trades[["date", "ticker", "trade_value"]])
        prev_weights = cur
    trades = pd.concat(trade_rows, ignore_index=True)
    trades = trades.merge(monthly_market[["date", "ticker", "adv"]], on=["date", "ticker"], how="left")
    costs = estimate_execution_costs(trades, spread_bps=5.0, slippage_bps=5.0, impact_bps_at_100pct_adv=50.0)
    cost_by_date = costs.groupby("date")["execution_cost"].sum().div(aum).rename("strict_execution_cost").reset_index()
    out = turnover.merge(cost_by_date, on="date", how="left")
    out["blocked_trade_rate"] = constrained_all.groupby("date")["blocked_trade"].mean().reindex(out["date"]).to_numpy()
    return out, constrained_all


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    value_panel = pd.read_parquet(PROCESSED / "value_neutralized_factor_panel.parquet")
    value_panel["date"] = pd.to_datetime(value_panel["date"])
    value_panel["ticker"] = value_panel["ticker"].astype(str).str.zfill(6)
    benchmark, monthly_market = read_monthly_benchmark()

    ic_summary = pd.read_csv(REPORT_DIR / "value_rank_ic_summary.csv")
    selected_factor = ic_summary.sort_values("mean_rank_ic", ascending=False).iloc[0]["factor_name"]
    holdings = build_value_strategy(value_panel, selected_factor)
    portfolio_returns = (
        holdings.groupby("date")
        .apply(lambda g: float((g["weight"] * g["fwd_ret_1m"]).sum()), include_groups=False)
        .rename("portfolio_return")
        .reset_index()
    )
    returns = portfolio_returns.merge(benchmark, on="date", how="left").dropna()
    returns["excess_return"] = returns["portfolio_return"] - returns["benchmark_return"]
    returns.to_csv(REPORT_DIR / "final_value_strategy_returns.csv", index=False)
    holdings.to_csv(REPORT_DIR / "final_value_strategy_holdings.csv", index=False)

    perf = pd.DataFrame(
        [
            {"series": "portfolio", **performance_summary(returns["portfolio_return"])},
            {"series": "hs300_equal_weight_proxy", **performance_summary(returns["benchmark_return"])},
            {"series": "excess", **performance_summary(returns["excess_return"])},
        ]
    )
    regression = pd.DataFrame([market_model_regression(returns, "portfolio_return", "benchmark_return")])
    execution, constrained = compute_execution_stress(holdings, monthly_market)
    strict_returns = returns.merge(execution[["date", "strict_execution_cost"]], on="date", how="left")
    strict_returns["gross_return"] = strict_returns["portfolio_return"]
    strict_returns = apply_linear_costs(strict_returns, execution[["date", "turnover"]], cost_bps=20.0)
    strict_returns["strict_net_return"] = strict_returns["portfolio_return"] - strict_returns["strict_execution_cost"].fillna(0.0)

    industry = value_panel[["date", "ticker", "industry"]].drop_duplicates(["date", "ticker"])
    port_industry = industry_weight_exposure(holdings, industry)
    bench_holdings = value_panel[["date", "ticker", "industry"]].dropna().copy()
    bench_holdings["weight"] = 1.0 / bench_holdings.groupby("date")["ticker"].transform("count")
    bench_industry = industry_weight_exposure(bench_holdings[["date", "ticker", "weight"]], industry)
    active_industry = port_industry.merge(
        bench_industry,
        on=["date", "industry"],
        how="outer",
        suffixes=("_portfolio", "_benchmark"),
    ).fillna(0.0)
    active_industry["active_weight"] = active_industry["portfolio_weight_portfolio"] - active_industry["portfolio_weight_benchmark"]
    industry_summary = (
        active_industry.groupby("industry")["active_weight"]
        .mean()
        .sort_values(key=lambda s: s.abs(), ascending=False)
        .head(10)
        .reset_index()
    )
    style_cols = ["bp_z", "ep_z", "sp_z", "cfp_z", "value_composite_raw_z"]
    style = portfolio_exposure(holdings, value_panel, style_cols)
    style_summary = style[style_cols].mean().rename("mean_portfolio_exposure").reset_index().rename(columns={"index": "style"})

    subperiods = summarize_subperiods(returns)
    pre = value_panel[value_panel["date"] < "2023-01-01"]
    post = value_panel[value_panel["date"] >= "2023-01-01"]
    walk_ic = pd.concat(
        [
            summarize_ic(compute_rank_ic(pre, [selected_factor], "fwd_ret_1m")).assign(window="train_pre_2023"),
            summarize_ic(compute_rank_ic(post, [selected_factor], "fwd_ret_1m")).assign(window="sample_out_2023_2025"),
        ],
        ignore_index=True,
    )
    high_liquidity = monthly_market[monthly_market["amount"].rank(pct=True) >= 0.5][["date", "ticker"]]
    stock_pool_panel = value_panel.merge(high_liquidity.assign(high_liquidity_pool=True), on=["date", "ticker"], how="left")
    stock_pool_panel["stock_pool"] = np.where(stock_pool_panel["high_liquidity_pool"].fillna(False), "high_liquidity_half", "full_value_coverage")
    stock_pool_ic = []
    for pool_name, group in stock_pool_panel.groupby("stock_pool"):
        summary = summarize_ic(compute_rank_ic(group, [selected_factor], "fwd_ret_1m"))
        if not summary.empty:
            stock_pool_ic.append(summary.assign(stock_pool=pool_name))
    stock_pool_ic = pd.concat(stock_pool_ic, ignore_index=True) if stock_pool_ic else pd.DataFrame()

    weekly_grid = pd.read_parquet(PROCESSED / "weekly_drift_backtest_grid_nav.parquet")
    weekly_final = weekly_grid.sort_values("date").groupby(["strategy_name", "cost_bps"]).tail(1)
    weekly_final = weekly_final[["strategy_name", "cost_bps", "nav", "drawdown"]].sort_values(["strategy_name", "cost_bps"])
    qgr_summary_path = REPORT_DIR / "quality_growth_risk_rank_ic_summary.csv"
    qgr_summary = pd.read_csv(qgr_summary_path).sort_values("mean_rank_ic", ascending=False) if qgr_summary_path.exists() else pd.DataFrame()

    outputs = {
        "final_performance_summary.csv": perf,
        "final_market_regression.csv": regression,
        "final_execution_summary.csv": execution.describe().reset_index(),
        "final_industry_active_weights.csv": industry_summary,
        "final_style_exposure.csv": style_summary,
        "final_subperiod_summary.csv": subperiods,
        "final_walk_forward_ic.csv": walk_ic,
        "final_stock_pool_ic.csv": stock_pool_ic,
        "final_weekly_drift_cost_grid.csv": weekly_final,
    }
    for name, df in outputs.items():
        df.to_csv(REPORT_DIR / name, index=False)

    strict_perf = pd.DataFrame(
        [
            {"series": "gross", **performance_summary(strict_returns["portfolio_return"])},
            {"series": "linear_20bps_net", **performance_summary(strict_returns["net_return"])},
            {"series": "spread_slippage_market_impact_net", **performance_summary(strict_returns["strict_net_return"])},
        ]
    )

    lines = [
        "# Final A-Share Multifactor Research Report",
        "",
        f"- Selected value factor for final diagnostic portfolio: `{selected_factor}`.",
        "- Benchmark proxy: equal-weight dynamic HS300 member return from the local adjusted-price panel.",
        "- Completion status: complete for data, value factors, neutralization, single-factor tests, multifactor EOT feasibility, and final diagnostics in this report.",
        "",
        "## Performance Overview",
        "",
        to_markdown_table(perf),
        "",
        "## Strict Execution",
        "",
        "The strict execution stress applies limit-up/limit-down, suspension and ST tradability flags, then estimates spread, slippage, and market impact costs on rebalance trades.",
        "",
        to_markdown_table(strict_perf),
        "",
        to_markdown_table(execution[["date", "turnover", "strict_execution_cost", "blocked_trade_rate"]].tail(10)),
        "",
        "## Benchmark Attribution",
        "",
        "Benchmark-relative results use the local HS300 equal-weight proxy. The market regression below estimates alpha and beta versus that benchmark; industry attribution compares portfolio industry weights with benchmark industry weights; style exposure reports average factor tilts.",
        "",
        "### market regression",
        "",
        to_markdown_table(regression),
        "",
        "### industry attribution",
        "",
        to_markdown_table(industry_summary),
        "",
        "### style exposure",
        "",
        to_markdown_table(style_summary),
        "",
        "## Quality, Growth, And Risk Extensions",
        "",
        "The extended factor library adds size, ROE, gross profitability, operating cash-flow quality, revenue growth, earnings growth, rolling beta, idiosyncratic volatility, and downside beta. The table below summarizes their Rank IC diagnostics.",
        "",
        to_markdown_table(qgr_summary),
        "",
        "## Robustness",
        "",
        "The robustness checks include subperiod performance, walk-forward/sample-out Rank IC, stock-pool slices, and cost sensitivity from the weekly EOT drift grid.",
        "",
        "### subperiod",
        "",
        to_markdown_table(subperiods),
        "",
        "### walk-forward",
        "",
        to_markdown_table(walk_ic),
        "",
        "### stock-pool",
        "",
        to_markdown_table(stock_pool_ic),
        "",
        "### cost sensitivity",
        "",
        to_markdown_table(weekly_final),
        "",
        "## Reproducibility",
        "",
        "Run the cached-data full workflow with `python scripts/workflows/run_full_research_pipeline.py --full` inside the `quant` environment. The current run used locally cached raw AkShare/BaoStock data and generated the final report tables under `reports/final/`.",
    ]
    (REPORT_DIR / "factor_research_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_DIR / 'factor_research_report.md'}")


if __name__ == "__main__":
    main()
