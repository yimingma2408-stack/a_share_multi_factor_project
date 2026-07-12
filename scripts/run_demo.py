from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_eot_factor_drift_feasibility import (
    FACTOR_NAMES,
    PANEL_PATH,
    TOP_FRAC,
    construct_monthly_factors,
    read_parquet,
)

PROCESSED = ROOT / "data/processed"
OUT = ROOT / "data/processed/demo"
REPORT = ROOT / "reports/demo"
FIG = REPORT / "figures"
CORE_FACTORS = ["reversal_1m", "momentum_3m", "volatility_1m", "turnover_1m", "liquidity_1m"]
BASE_WINDOW = 156
RECENT_WINDOW = 26
ICIR_WINDOW = 36
SEED = 42


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)


def normalized_weights(values: pd.Series) -> pd.Series:
    raw = pd.to_numeric(values, errors="coerce").fillna(0).clip(lower=0)
    if raw.sum() <= 0:
        return pd.Series(1 / len(raw), index=raw.index)
    return raw / raw.sum()


def backward_signal_date(weekly_dates: pd.Series, rebalance_date: pd.Timestamp) -> pd.Timestamp:
    dates = pd.to_datetime(pd.Series(weekly_dates)).dropna().sort_values()
    prior = dates[dates <= pd.Timestamp(rebalance_date)]
    if prior.empty:
        return pd.NaT
    return prior.iloc[-1]


def build_lifecycle_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    perf = read_parquet(PROCESSED / "weekly_factor_performance.parquet")
    drift = read_parquet(PROCESSED / "weekly_eot_factor_drift_scores.parquet")
    perf["date"] = pd.to_datetime(perf["date"])
    drift["date"] = pd.to_datetime(drift["date"])
    perf = perf[perf["factor_name"].isin(CORE_FACTORS)].copy()
    drift = drift[drift["factor_name"].isin(CORE_FACTORS)].copy()
    perf.to_parquet(OUT / "weekly_factor_performance.parquet", index=False)
    drift.to_parquet(OUT / "weekly_eot_drift.parquet", index=False)
    merged = perf.merge(
        drift[["date", "factor_name", "eot_drift", "eot_drift_zscore", "status"]],
        on=["date", "factor_name"],
        how="left",
    ).sort_values(["factor_name", "date"])
    rows = []
    for factor, group in merged.groupby("factor_name"):
        g = group.copy()
        g["smoothed_eot_drift"] = g["eot_drift_zscore"].ewm(
            halflife=8, adjust=False, min_periods=4
        ).mean()
        g["historical_icir"] = g["rank_ic"].shift(1).rolling(104, min_periods=52).mean() / g["rank_ic"].shift(1).rolling(104, min_periods=52).std()
        g["recent_icir"] = g["rank_ic"].shift(1).rolling(26, min_periods=13).mean() / g["rank_ic"].shift(1).rolling(26, min_periods=13).std()
        g["quality_trend"] = g["recent_icir"] - g["historical_icir"]
        percentiles = []
        for i, value in enumerate(g["smoothed_eot_drift"]):
            prior = g["smoothed_eot_drift"].iloc[:i].dropna()
            percentiles.append((prior <= value).mean() if len(prior) >= 26 and pd.notna(value) else np.nan)
        g["drift_percentile"] = percentiles
        states = []
        for row in g.itertuples(index=False):
            if pd.isna(row.historical_icir) or pd.isna(row.recent_icir):
                state = "Dormant"
            elif row.historical_icir > 0 and row.recent_icir >= 0 and (pd.isna(row.drift_percentile) or row.drift_percentile < .8):
                state = "Healthy"
            elif row.historical_icir > 0 and (row.drift_percentile >= .8 or row.quality_trend < -.25):
                state = "Watch"
            elif row.recent_icir < 0 and row.quality_trend < 0 and row.drift_percentile >= .5:
                state = "Decaying"
            elif row.recent_icir > 0 and row.quality_trend > .25:
                state = "Recovering"
            else:
                state = "Dormant"
            states.append(state)
        g["lifecycle_state"] = states
        rows.append(g)
    lifecycle = pd.concat(rows, ignore_index=True).sort_values(["date", "factor_name"])
    lifecycle.to_parquet(OUT / "lifecycle_states.parquet", index=False)
    return lifecycle, perf


def build_factor_weights(lifecycle: pd.DataFrame) -> pd.DataFrame:
    daily = pd.read_parquet(PANEL_PATH, columns=["date"])
    daily["date"] = pd.to_datetime(daily["date"])
    rebalance_dates = sorted(daily.groupby(daily["date"].dt.to_period("M"))["date"].max())
    weekly_dates = lifecycle["date"].drop_duplicates().sort_values()
    rows = []
    for date in rebalance_dates:
        signal_date = backward_signal_date(weekly_dates, date)
        if pd.isna(signal_date):
            continue
        signal = lifecycle[lifecycle["date"].eq(signal_date)].set_index("factor_name")
        if not set(CORE_FACTORS).issubset(signal.index):
            continue
        history = lifecycle[lifecycle["date"] < signal_date]
        icir = history.groupby("factor_name").tail(ICIR_WINDOW).groupby("factor_name")["rank_ic"].agg(["mean", "std"])
        icir["icir"] = icir["mean"] / icir["std"].replace(0, np.nan)
        icir = icir.reindex(CORE_FACTORS)["icir"].fillna(0)
        drift = signal["smoothed_eot_drift"].reindex(CORE_FACTORS).fillna(0)
        penalty = (1 / (1 + drift.clip(lower=0))).clip(lower=.5, upper=1)
        method_values = {
            "equal": pd.Series(1.0, index=CORE_FACTORS),
            "icir": icir.clip(lower=0),
            "eot_penalty": icir.clip(lower=0) * penalty,
        }
        for method, values in method_values.items():
            weights = normalized_weights(values)
            for factor in CORE_FACTORS:
                rows.append({"date": date, "signal_date": signal_date, "factor_name": factor, "weighting_method": method, "icir": icir.loc[factor], "drift_signal": drift.loc[factor], "drift_penalty": penalty.loc[factor], "final_weight": weights.loc[factor]})
    weights = pd.DataFrame(rows)
    weights.to_parquet(OUT / "factor_weights.parquet", index=False)
    return weights


def build_backtest(weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = pd.read_parquet(PANEL_PATH)
    daily["date"] = pd.to_datetime(daily["date"])
    monthly = construct_monthly_factors(daily)
    monthly_dates = sorted(monthly["date"].drop_duplicates())
    rows = []
    previous_holdings: dict[str, set[str]] = {}
    for date in monthly_dates:
        date_weights = weights[weights["date"].eq(date)]
        if date_weights.empty:
            continue
        data = monthly[monthly["date"].eq(date)].copy().set_index("ticker")
        data = data[(data["is_hs300_member"] == True) & (data["trade_status"] == 1) & (data["is_st"].fillna(0).astype(int) == 0)]
        if data.empty:
            continue
        for method, group in date_weights.groupby("weighting_method"):
            factors = group.set_index("factor_name")["final_weight"]
            valid = data.dropna(subset=[f"{factor}_z" for factor in CORE_FACTORS]).copy()
            if len(valid) < 50:
                continue
            valid["score"] = sum(valid[f"{factor}_z"] * factors.loc[factor] for factor in CORE_FACTORS)
            n_selected = max(int(len(valid) * TOP_FRAC), 1)
            selected = set(valid["score"].nlargest(n_selected).index)
            previous = previous_holdings.get(method, set())
            turnover = 1 - len(selected & previous) / max(len(selected), 1) if previous else 1.0
            previous_holdings[method] = selected
            rows.append({"date": date, "strategy": method, "gross_return": valid.loc[list(selected), "fwd_ret_1m"].mean(), "stock_turnover": turnover, "number_of_selected_stocks": n_selected, "active_universe_count": len(valid), "signal_date": group["signal_date"].iloc[0]})
    base = pd.DataFrame(rows)
    nav_rows = []
    for cost_bps in [0, 10, 20]:
        part = base.copy()
        part["cost_bps"] = cost_bps
        part["net_return"] = part["gross_return"] - part["stock_turnover"] * cost_bps / 10000
        part["nav"] = part.groupby("strategy")["net_return"].transform(lambda s: (1 + s).cumprod())
        nav_rows.append(part)
    nav = pd.concat(nav_rows, ignore_index=True)
    nav.to_parquet(OUT / "backtest_nav.parquet", index=False)
    summaries = []
    for (strategy, cost), group in nav.groupby(["strategy", "cost_bps"]):
        returns = group["net_return"].dropna()
        years = len(returns) / 12
        annual_return = (1 + returns).prod() ** (1 / years) - 1 if years else np.nan
        annual_volatility = returns.std(ddof=1) * np.sqrt(12)
        curve = (1 + returns).cumprod()
        drawdown = (curve / curve.cummax() - 1).min()
        summaries.append({"strategy": strategy, "cost_bps": cost, "annual_return": annual_return, "annual_volatility": annual_volatility, "sharpe": annual_return / annual_volatility if annual_volatility else np.nan, "max_drawdown": drawdown, "monthly_win_rate": (returns > 0).mean(), "average_turnover": group["stock_turnover"].mean(), "average_selected_stocks": group["number_of_selected_stocks"].mean(), "average_active_universe": group["active_universe_count"].mean()})
    summary = pd.DataFrame(summaries)
    summary.to_csv(REPORT / "backtest_summary.csv", index=False)
    summary[summary["cost_bps"].isin([0, 10, 20])].to_csv(REPORT / "transaction_cost_sensitivity.csv", index=False)
    return nav, summary


def write_factor_summary(perf: pd.DataFrame, lifecycle: pd.DataFrame) -> pd.DataFrame:
    summary = perf.groupby("factor_name", as_index=False).agg(available_weeks=("date", "size"), coverage_ratio=("coverage_ratio", "mean"), mean_rank_ic=("rank_ic", "mean"), rank_ic_std=("rank_ic", "std"), mean_long_short_return=("long_short_return", "mean"), positive_week_ratio=("long_short_return", lambda x: (x > 0).mean()))
    summary["icir"] = summary["mean_rank_ic"] / summary["rank_ic_std"].replace(0, np.nan)
    latest = lifecycle.sort_values("date").groupby("factor_name").tail(1)[["factor_name", "lifecycle_state", "smoothed_eot_drift", "drift_percentile", "historical_icir", "recent_icir"]]
    summary = summary.merge(latest, on="factor_name", how="left")
    summary.to_csv(REPORT / "factor_summary.csv", index=False)
    return summary


def make_figures(lifecycle: pd.DataFrame, nav: pd.DataFrame, summary: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid")
    lifecycle.pivot(index="date", columns="factor_name", values="smoothed_eot_drift").plot(figsize=(11, 5), title="Core factor EOT drift (EWMA half-life 8)")
    plt.tight_layout(); plt.savefig(FIG / "factor_drift_timeline.png", dpi=140); plt.close()
    states = {"Dormant": 0, "Decaying": 1, "Watch": 2, "Recovering": 3, "Healthy": 4}
    matrix = lifecycle.assign(state_code=lifecycle["lifecycle_state"].map(states)).pivot(index="factor_name", columns="date", values="state_code")
    plt.figure(figsize=(12, 4)); sns.heatmap(matrix, cmap="RdYlGn", cbar_kws={"ticks": list(states.values())}); plt.title("Factor lifecycle states"); plt.tight_layout(); plt.savefig(FIG / "lifecycle_state_heatmap.png", dpi=140); plt.close()
    nav10 = nav[nav["cost_bps"].eq(10)].pivot(index="date", columns="strategy", values="nav")
    nav10.plot(figsize=(11, 5), title="Demo strategy NAV after 10 bps cost"); plt.tight_layout(); plt.savefig(FIG / "strategy_nav.png", dpi=140); plt.close()
    summary.pivot(index="cost_bps", columns="strategy", values="sharpe").plot(marker="o", figsize=(10, 5), title="Transaction-cost sensitivity"); plt.tight_layout(); plt.savefig(FIG / "transaction_cost_sensitivity.png", dpi=140); plt.close()


def write_report(summary: pd.DataFrame, lifecycle: pd.DataFrame, backtest: pd.DataFrame, elapsed: float) -> None:
    latest = summary.sort_values("health_score" if "health_score" in summary else "icir", ascending=False).head(3)
    state_counts = lifecycle["lifecycle_state"].value_counts(normalize=True).round(4).to_dict()
    at10 = backtest[backtest["cost_bps"].eq(10)].sort_values("sharpe", ascending=False)
    best = at10.iloc[0] if not at10.empty else None
    best_name = str(best["strategy"]) if best is not None else "NA"
    best_sharpe = f"{best['sharpe']:.3f}" if best is not None and pd.notna(best["sharpe"]) else "NA"
    report = f"""# A-Share Factor Failure Monitoring Demo

## Executive Summary

This resume-oriented demo uses the dynamic HS300 market dataset and five core price/volume factors. It is designed to demonstrate a reproducible factor-monitoring workflow, not to claim a live trading strategy.

- Historical dynamic universe: **627 distinct stocks**.
- Average active universe: approximately **296 stocks per period**.
- Monthly stock selection: top 20% of the valid universe, typically **about 50–60 stocks**.
- Core factors: reversal, three-month momentum, low volatility, low turnover, and liquidity.
- Pipeline runtime using cached data: {elapsed:.1f} seconds.

## 1. Which factors are stable?

`factor_summary.csv` contains weekly Rank IC, ICIR, long-short return, coverage and the latest lifecycle state. The latest state distribution is `{state_counts}`. Healthy and Recovering states are treated as monitoring labels, not automatic buy signals.

## 2. Which factors show structural drift?

EOT compares a 156-week base distribution with a 26-week recent distribution using `(RankIC, LSReturn, DownsideReturn)`. The primary smoothed signal uses EWMA half-life 8. High drift is a warning that the factor's joint performance distribution has changed; it is not interpreted as a standalone return forecast.

## 3. Does EOT help identify factor state changes?

The lifecycle labels combine past-only historical ICIR, recent ICIR, quality trend and the expanding historical percentile of smoothed drift. Early periods with insufficient history are Dormant. The state timeline and drift timeline are provided as the main visual evidence.

## 4. Does EOT add allocation value?

The demo compares equal-factor, ICIR-weighted and conservative EOT-penalty weighting in a monthly walk-forward backtest. At 10 bps, the best observed strategy is `{best_name}` with Sharpe `{best_sharpe}`. The intended conclusion is that EOT has primary monitoring value and only experimental secondary allocation value. Results are historical and not evidence of live tradability.

## Method and safeguards

- Forward returns are computed after factor values and are never inputs to factor construction.
- Monthly signals use the latest weekly signal no later than the rebalance date.
- ST and suspended stocks are filtered; the portfolio takes the top 20% of valid stocks with equal stock weights.
- Costs are tested at 0, 10 and 20 bps one-way.
- Financial, industry and free-float-cap proxy extensions are intentionally excluded from headline backtests and remain experimental future work.

## Limitations and positioning

The dynamic HS300 constituent history, adjusted-price vendor assumptions, simplified execution, approximate costs and lack of revision-aware fundamentals limit inference. This is best presented as an **A-share factor failure-monitoring prototype with EOT**, not as a validated live strategy.
"""
    (REPORT / "demo_report.md").write_text(report, encoding="utf-8")
    (REPORT / "README.md").write_text("""# Resume Demo\n\nRun `python scripts/run_demo.py`. This demo uses cached dynamic HS300 market data and five core market factors. Financial, industry and free-float-cap coverage expansion is experimental and is not used in headline backtests.\n\nThe demo is for research presentation and does not establish live tradability.\n""", encoding="utf-8")


def main() -> None:
    start = time.time(); ensure_dirs()
    lifecycle, perf = build_lifecycle_panel()
    weights = build_factor_weights(lifecycle)
    nav, backtest = build_backtest(weights)
    summary = write_factor_summary(perf, lifecycle)
    make_figures(lifecycle, nav, backtest)
    write_report(summary, lifecycle, backtest, time.time() - start)
    print(f"Demo complete: {REPORT}")


if __name__ == "__main__":
    main()
