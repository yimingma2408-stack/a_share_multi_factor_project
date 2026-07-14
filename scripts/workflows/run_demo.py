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

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.eot.run_eot_factor_drift_feasibility import (
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
    lifecycle.pivot(index="date", columns="factor_name", values="smoothed_eot_drift").plot(figsize=(11, 5), title="Smoothed factor drift z-score (EWMA half-life 8 weeks)")
    plt.tight_layout(); plt.savefig(FIG / "factor_drift_timeline.png", dpi=140); plt.close()
    states = {"Dormant": 0, "Decaying": 1, "Watch": 2, "Recovering": 3, "Healthy": 4}
    matrix = lifecycle.assign(state_code=lifecycle["lifecycle_state"].map(states)).pivot(index="factor_name", columns="date", values="state_code")
    plt.figure(figsize=(12, 4)); sns.heatmap(matrix, cmap="RdYlGn", cbar_kws={"ticks": list(states.values())}); plt.title("Factor lifecycle states"); plt.tight_layout(); plt.savefig(FIG / "lifecycle_state_heatmap.png", dpi=140); plt.close()
    nav10 = nav[nav["cost_bps"].eq(10)].pivot(index="date", columns="strategy", values="nav")
    nav10.plot(figsize=(11, 5), title="Demo strategy NAV after 10 bps cost"); plt.tight_layout(); plt.savefig(FIG / "strategy_nav.png", dpi=140); plt.close()
    summary.pivot(index="cost_bps", columns="strategy", values="sharpe").plot(marker="o", figsize=(10, 5), title="Transaction-cost sensitivity"); plt.tight_layout(); plt.savefig(FIG / "transaction_cost_sensitivity.png", dpi=140); plt.close()


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a small DataFrame without requiring the optional tabulate package."""
    columns = [str(column) for column in frame.columns]
    rows = [[str(value).replace("|", "\\|") for value in row] for row in frame.itertuples(index=False, name=None)]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def write_report(
    factor_summary: pd.DataFrame,
    lifecycle: pd.DataFrame,
    backtest: pd.DataFrame,
    nav: pd.DataFrame,
    weights: pd.DataFrame,
    elapsed: float,
) -> None:
    latest = lifecycle.sort_values("date").groupby("factor_name").tail(1)
    latest = latest[["factor_name", "lifecycle_state", "historical_icir", "recent_icir", "eot_drift", "smoothed_eot_drift", "drift_percentile"]]
    factor_view = factor_summary[["factor_name", "coverage_ratio", "mean_rank_ic", "icir"]].merge(
        latest, on="factor_name", how="left"
    ).sort_values("icir", ascending=False)
    factor_table = factor_view.rename(columns={
        "factor_name": "Factor", "coverage_ratio": "Coverage", "mean_rank_ic": "Mean Rank IC",
        "icir": "Full ICIR", "lifecycle_state": "Latest state", "historical_icir": "Historical ICIR",
        "recent_icir": "Recent ICIR", "eot_drift": "Raw drift", "smoothed_eot_drift": "Smoothed drift z-score",
        "drift_percentile": "Drift percentile",
    })
    for column in ["Coverage", "Drift percentile"]:
        factor_table[column] = factor_table[column].map(lambda x: f"{x:.1%}" if pd.notna(x) else "NA")
    for column in ["Mean Rank IC", "Full ICIR", "Historical ICIR", "Recent ICIR", "Raw drift", "Smoothed drift z-score"]:
        factor_table[column] = factor_table[column].map(lambda x: f"{x:.3f}" if pd.notna(x) else "NA")

    at10 = backtest[backtest["cost_bps"].eq(10)].sort_values("sharpe", ascending=False).copy()
    backtest_table = at10[["strategy", "annual_return", "annual_volatility", "sharpe", "max_drawdown", "monthly_win_rate", "average_turnover"]].rename(columns={
        "strategy": "Strategy", "annual_return": "Annual return", "annual_volatility": "Annual volatility",
        "sharpe": "Sharpe*", "max_drawdown": "Max drawdown", "monthly_win_rate": "Monthly win rate",
        "average_turnover": "Average turnover",
    })
    for column in ["Annual return", "Annual volatility", "Max drawdown", "Monthly win rate", "Average turnover"]:
        backtest_table[column] = backtest_table[column].map(lambda x: f"{x:.1%}" if pd.notna(x) else "NA")
    backtest_table["Sharpe*"] = backtest_table["Sharpe*"].map(lambda x: f"{x:.3f}" if pd.notna(x) else "NA")

    cost_view = backtest.pivot(index="strategy", columns="cost_bps", values="annual_return").reindex(columns=[0, 10, 20])
    cost_view.columns = ["0 bps", "10 bps", "20 bps"]
    cost_view = cost_view.reset_index().rename(columns={"strategy": "Strategy"})
    for column in ["0 bps", "10 bps", "20 bps"]:
        cost_view[column] = cost_view[column].map(lambda x: f"{x:.1%}" if pd.notna(x) else "NA")

    latest_weight_date = pd.to_datetime(weights["date"]).max()
    weight_view = weights[(weights["date"].eq(latest_weight_date)) & weights["weighting_method"].isin(["icir", "eot_penalty"])]
    weight_view = weight_view.pivot(index="factor_name", columns="weighting_method", values="final_weight").reindex(CORE_FACTORS).reset_index()
    weight_view = weight_view.rename(columns={"factor_name": "Factor", "icir": "ICIR weight", "eot_penalty": "EOT-penalty weight"})
    for column in ["ICIR weight", "EOT-penalty weight"]:
        weight_view[column] = weight_view[column].map(lambda x: f"{x:.1%}" if pd.notna(x) else "NA")

    best = at10.iloc[0]
    best_name = str(best["strategy"])
    best_sharpe = float(best["sharpe"])
    long_term_best = factor_view.iloc[0]
    watch_names = factor_view.loc[factor_view["lifecycle_state"].eq("Watch"), "factor_name"].tolist()
    highest_drift = factor_view.sort_values("drift_percentile", ascending=False).iloc[0]
    icir10 = at10.set_index("strategy").loc["icir"]
    eot10 = at10.set_index("strategy").loc["eot_penalty"]
    eot_sharpe_delta = float(eot10["sharpe"] - icir10["sharpe"])
    eot_return_delta = float(eot10["annual_return"] - icir10["annual_return"])

    panel_tickers = pd.read_parquet(PANEL_PATH, columns=["ticker"])["ticker"].nunique()
    drift_metadata = read_parquet(PROCESSED / "weekly_eot_factor_drift_scores.parquet")
    drift_status = drift_metadata["status"].value_counts(normalize=True)
    fallback_share = float(drift_status.get("fallback", 0.0))
    base_observations = int(drift_metadata["n_base"].mode().iloc[0])
    recent_observations = int(drift_metadata["n_recent"].mode().iloc[0])
    drift_implementation = (
        f"{fallback_share:.0%} of cached observations use the covariance/mean-shift fallback because POT was unavailable when the drift file was generated"
        if fallback_share > 0
        else "the cached observations use the EOT barycentric-map implementation"
    )
    nav_dates = pd.to_datetime(nav["date"])
    unique_months = nav_dates.nunique()
    active_min = int(nav["active_universe_count"].min())
    active_max = int(nav["active_universe_count"].max())
    selected_min = int(nav["number_of_selected_stocks"].min())
    selected_max = int(nav["number_of_selected_stocks"].max())
    latest_date = pd.to_datetime(lifecycle["date"]).max().date().isoformat()
    watch_text = ", ".join(f"`{name}`" for name in watch_names) if watch_names else "none"
    allocation_verdict = "did not improve on" if eot_sharpe_delta <= 0 else "improved on"

    report = f"""# A-Share Factor Failure Monitoring Demo

## Executive summary

This demo evaluates five price/volume factors in the dynamic HS300 universe and uses an EOT-style distribution-drift signal as a factor-failure monitor. The evidence supports a cautious conclusion: the monitoring layer identifies meaningful deterioration, but the drift-based allocation overlay is not yet a performance improvement.

- **Sample:** {nav_dates.min().date().isoformat()} to {nav_dates.max().date().isoformat()}, {unique_months} monthly observations and {panel_tickers} distinct historical constituents.
- **Portfolio breadth:** {active_min}–{active_max} eligible stocks per rebalance; the top 20% rule selected {selected_min}–{selected_max} stocks.
- **Current warning:** {watch_text} are in `Watch` as of {latest_date}.
- **Backtest headline:** at 10 bps, `{best_name}` ranked first with {best["annual_return"]:.1%} annualized return, {best_sharpe:.3f} Sharpe and {best["max_drawdown"]:.1%} maximum drawdown.
- **EOT allocation result:** EOT-penalty weighting {allocation_verdict} plain ICIR weighting; the Sharpe difference was {eot_sharpe_delta:+.3f} and annual-return difference was {eot_return_delta:+.1%} at 10 bps.
- **Implementation disclosure:** {drift_implementation}; these results should therefore be described as fallback drift diagnostics, not full EOT-map estimates.
- Cached pipeline runtime: {elapsed:.1f} seconds.

## 1. Factor evidence and current lifecycle state

The full-sample factor statistics and latest monitoring signals are shown below. `Full ICIR` is descriptive over the entire sample; the historical and recent ICIR inputs used for the state label are lagged to avoid look-ahead. `Raw drift` is a distance and is therefore non-negative. `Smoothed drift z-score` standardizes raw drift against the factor's own prior expanding history and then applies an 8-week-half-life EWMA, so it can be negative when current drift is below its historical norm.

{markdown_table(factor_table)}

The strongest full-sample Rank IC consistency came from `{long_term_best["factor_name"]}` (ICIR {long_term_best["icir"]:.3f}). The latest snapshot nevertheless shows that {watch_text} have moved from positive historical ICIR to negative recent ICIR, which is direct evidence of deterioration rather than merely high EOT distance. `{highest_drift["factor_name"]}` has the highest current drift percentile ({highest_drift["drift_percentile"]:.1%}); because its state is `{highest_drift["lifecycle_state"]}`, drift should be interpreted as distribution change, not automatically as factor decay.

![Smoothed factor drift z-score by factor](figures/factor_drift_timeline.png)

## 2. What the lifecycle chart says

The drift input compares a {base_observations}-week base distribution with a {recent_observations}-week recent distribution of Rank IC, long-short return and downside return. The lifecycle model then combines lagged 104-week historical ICIR, lagged 26-week recent ICIR, their change, and the expanding percentile of EWMA-smoothed drift. Early observations without enough history are `Dormant`, so the heatmap should be read from left to right rather than by comparing raw counts of states.

![Factor lifecycle states](figures/lifecycle_state_heatmap.png)

The chart's practical use is monitoring: it separates persistent healthy periods from episodes that deserve review. It does not turn a `Healthy` label into a buy signal or a `Watch` label into an automatic exclusion.

## 3. Walk-forward backtest

The table reports the three allocation rules after a 10 bps one-way turnover charge.

{markdown_table(backtest_table)}

![Strategy NAV after 10 bps cost](figures/strategy_nav.png)

At this cost assumption, `{best_name}` delivered the highest risk-adjusted result. EOT-penalty weighting produced {eot10["annual_return"]:.1%} annualized return and {eot10["sharpe"]:.3f} Sharpe versus {icir10["annual_return"]:.1%} and {icir10["sharpe"]:.3f} for ICIR weighting. Therefore, this run supports distribution drift as a diagnostic overlay, but not the claim that the current penalty function adds allocation value.

The latest weights also illustrate the mechanism: the drift penalty only scales non-negative ICIR signals, with a penalty floor of 0.5.

{markdown_table(weight_view)}

## 4. Transaction-cost sensitivity

Annualized return declines monotonically as the assumed one-way cost rises from 0 to 20 bps:

{markdown_table(cost_view)}

![Transaction-cost sensitivity](figures/transaction_cost_sensitivity.png)

The strategies retain positive historical annualized returns at 20 bps, but the gap between gross and net results is material because average monthly turnover is roughly 45%–49%. This is a sensitivity check, not a complete execution model.

## Method and safeguards

- Factor values are constructed before one-month forward returns and never use those forward returns as inputs.
- Monthly rebalances use the latest weekly monitoring signal no later than the rebalance date.
- The active universe requires current HS300 membership, normal trading status and non-ST status.
- Five cross-sectional factor z-scores are combined, and the top 20% of valid stocks are equally weighted.
- `equal` uses equal factor weights; `icir` normalizes positive rolling ICIR; `eot_penalty` additionally scales positive ICIR by smoothed drift.
- The cached drift input uses {base_observations} base weeks and {recent_observations} recent weeks; {drift_implementation}.
- Costs are modeled as turnover multiplied by 0, 10 or 20 bps one-way.
- *Sharpe is implemented here as annualized compound return divided by annualized monthly volatility, with no risk-free-rate adjustment.*

## Limitations

The results depend on the reconstructed dynamic HS300 history, adjusted-price vendor conventions and a simplified monthly execution model. The backtest does not model limit-up/limit-down execution, market impact, liquidity capacity or point-in-time fundamental revisions. Industry, fundamentals and free-float-cap neutralization are not included. Most importantly, the current cached drift data use the fallback implementation noted above; full EOT barycentric-map results require regenerating that input with POT available. Thresholds and penalty strength are research choices and have not been validated out of sample.

Accordingly, this project is best presented as an **A-share factor failure-monitoring prototype with an experimental allocation overlay**, not as a validated live strategy.

## Reproducibility and artifacts

- Run: `python scripts/workflows/run_demo.py`
- Factor statistics: [`factor_summary.csv`](factor_summary.csv)
- Backtest statistics: [`backtest_summary.csv`](backtest_summary.csv)
- Cost sensitivity: [`transaction_cost_sensitivity.csv`](transaction_cost_sensitivity.csv)
- Machine-readable lifecycle, weights and NAV files: `../../data/processed/demo/`
"""
    (REPORT / "demo_report.md").write_text(report, encoding="utf-8")
    (REPORT / "README.md").write_text("""# Resume Demo\n\nRun `python scripts/workflows/run_demo.py`. This demo uses cached dynamic HS300 market data and five core market factors. Financial, industry and free-float-cap coverage expansion is experimental and is not used in headline backtests.\n\nThe demo is for research presentation and does not establish live tradability.\n""", encoding="utf-8")


def main() -> None:
    start = time.time(); ensure_dirs()
    lifecycle, perf = build_lifecycle_panel()
    weights = build_factor_weights(lifecycle)
    nav, backtest = build_backtest(weights)
    summary = write_factor_summary(perf, lifecycle)
    make_figures(lifecycle, nav, backtest)
    write_report(summary, lifecycle, backtest, nav, weights, time.time() - start)
    print(f"Demo complete: {REPORT}")


if __name__ == "__main__":
    main()
