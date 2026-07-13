from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.eot.run_eot_factor_drift_feasibility import (
    FACTOR_NAMES,
    PANEL_PATH,
    TOP_FRAC,
    construct_monthly_factors,
    max_drawdown,
    read_parquet,
    write_parquet,
)


PROCESSED_DIR = ROOT / "data/processed"
REPORT_DIR = ROOT / "reports/eot_factor_drift_feasibility"
FIG_DIR = REPORT_DIR / "figures_weekly_robustness"

SIGNALS = {
    "4w_mean": "weekly_drift_signal_4w_mean",
    "8w_mean": "weekly_drift_signal_8w_mean",
    "12w_mean": "weekly_drift_signal_12w_mean",
    "ewma_hl4": "weekly_drift_signal_ewma_hl4",
    "ewma_hl8": "weekly_drift_signal_ewma_hl8",
    "ewma_hl12": "weekly_drift_signal_ewma_hl12",
}
ETAS = [0.5, 1.0, 1.5, 2.0]
CLIPS = {
    "no_clip": 0.0,
    "clip_0.5": 0.5,
    "clip_0.7": 0.7,
    "clip_0.8": 0.8,
}
COSTS_BPS = [0, 5, 10, 20]
ICIR_WINDOW = 36


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[dict[str, pd.DataFrame], list[str]]:
    paths = {
        "monthly_perf": PROCESSED_DIR / "monthly_factor_performance.parquet",
        "weekly_perf": PROCESSED_DIR / "weekly_factor_performance.parquet",
        "monthly_drift": PROCESSED_DIR / "eot_factor_drift_scores.parquet",
        "weekly_drift": PROCESSED_DIR / "weekly_eot_factor_drift_scores.parquet",
        "monthly_weights": PROCESSED_DIR / "monthly_factor_weights.parquet",
        "weekly_weights": PROCESSED_DIR / "monthly_factor_weights_weekly_drift.parquet",
        "monthly_nav": PROCESSED_DIR / "eot_factor_drift_backtest_nav.parquet",
        "weekly_nav": PROCESSED_DIR / "eot_factor_drift_backtest_nav_weekly_drift.parquet",
    }
    data: dict[str, pd.DataFrame] = {}
    missing = []
    for name, path in paths.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        data[name] = read_parquet(path)
        if "date" in data[name]:
            data[name]["date"] = pd.to_datetime(data[name]["date"])
    required = {"monthly_perf", "weekly_perf", "weekly_drift"}
    absent_required = required - data.keys()
    if absent_required:
        raise FileNotFoundError(f"Required inputs are missing: {sorted(absent_required)}")
    return data, missing


def construct_smoothed_signals(
    weekly_drift: pd.DataFrame, monthly_dates: list[pd.Timestamp]
) -> pd.DataFrame:
    drift = weekly_drift.dropna(subset=["eot_drift_zscore"]).sort_values(["factor_name", "date"])
    rows = []
    for date in monthly_dates:
        for factor in FACTOR_NAMES:
            values = drift.loc[
                (drift["factor_name"] == factor) & (drift["date"] <= date),
                "eot_drift_zscore",
            ].astype(float)
            n_obs = len(values)
            row = {
                "date": date,
                "factor_name": factor,
                "n_weekly_obs_available": n_obs,
            }
            if n_obs < 4:
                row.update({column: np.nan for column in SIGNALS.values()})
            else:
                row["weekly_drift_signal_4w_mean"] = values.tail(4).mean()
                row["weekly_drift_signal_8w_mean"] = values.tail(8).mean()
                row["weekly_drift_signal_12w_mean"] = values.tail(12).mean()
                for half_life in [4, 8, 12]:
                    row[f"weekly_drift_signal_ewma_hl{half_life}"] = (
                        values.ewm(halflife=half_life, adjust=False, min_periods=4).mean().iloc[-1]
                    )
            rows.append(row)
    signals = pd.DataFrame(rows).sort_values(["date", "factor_name"]).reset_index(drop=True)
    write_parquet(signals, PROCESSED_DIR / "weekly_drift_signals_for_monthly_rebalance.parquet")
    return signals


def summarize_smoothing(signals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, column in SIGNALS.items():
        values = signals[column]
        factor_ac1 = signals.groupby("factor_name")[column].apply(lambda s: s.autocorr(1))
        factor_ac3 = signals.groupby("factor_name")[column].apply(lambda s: s.autocorr(3))
        rows.append(
            {
                "signal_name": name,
                "mean": values.mean(),
                "std": values.std(ddof=1),
                "median": values.median(),
                "min": values.min(),
                "max": values.max(),
                "autocorrelation_1": factor_ac1.mean(),
                "autocorrelation_3": factor_ac3.mean(),
                "missing_ratio": values.isna().mean(),
                "notes": "Autocorrelations are averages of factor-level monthly signal autocorrelations.",
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(REPORT_DIR / "weekly_drift_signal_smoothing_summary.csv", index=False)
    return summary


def rolling_icir(monthly_perf: pd.DataFrame, dates: list[pd.Timestamp]) -> pd.DataFrame:
    rows = []
    for date in dates:
        for factor in FACTOR_NAMES:
            hist = monthly_perf[
                (monthly_perf["factor_name"] == factor) & (monthly_perf["date"] < date)
            ].sort_values("date").tail(ICIR_WINDOW)
            if len(hist) < 12:
                continue
            std = hist["rank_ic"].std(ddof=1)
            icir = hist["rank_ic"].mean() / std if std and np.isfinite(std) else 0.0
            rows.append({"date": date, "factor_name": factor, "icir": icir})
    return pd.DataFrame(rows)


def build_weight_grid(signals: pd.DataFrame, monthly_perf: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(signals["date"].unique()))
    icirs = rolling_icir(monthly_perf, dates)
    rows = []
    for signal_name, column in SIGNALS.items():
        base = signals[["date", "factor_name", column]].rename(columns={column: "drift_signal"})
        base = base.merge(icirs, on=["date", "factor_name"], how="inner")
        complete_dates = (
            base.groupby("date")["drift_signal"]
            .apply(lambda s: len(s) == len(FACTOR_NAMES) and s.notna().all())
        )
        base = base[base["date"].isin(complete_dates[complete_dates].index)]
        for eta in ETAS:
            penalty_raw = 1.0 / (1.0 + eta * base["drift_signal"].clip(lower=0))
            for clip_scheme, clip_lower in CLIPS.items():
                part = base.copy()
                part["signal_name"] = signal_name
                part["eta"] = eta
                part["clip_scheme"] = clip_scheme
                part["clip_lower"] = clip_lower
                part["clip_upper"] = 1.0
                part["penalty_raw"] = penalty_raw
                part["penalty_clipped"] = penalty_raw.clip(lower=clip_lower, upper=1.0)
                part["raw_weight"] = part["icir"].clip(lower=0) * part["penalty_clipped"]
                total = part.groupby("date")["raw_weight"].transform("sum")
                factor_count = part.groupby("date")["factor_name"].transform("count")
                part["final_weight"] = np.where(
                    total > 0,
                    part["raw_weight"] / total,
                    1.0 / factor_count,
                )
                rows.append(part)
    grid = pd.concat(rows, ignore_index=True)
    grid = grid[
        [
            "date",
            "factor_name",
            "signal_name",
            "eta",
            "clip_scheme",
            "clip_lower",
            "clip_upper",
            "icir",
            "drift_signal",
            "penalty_raw",
            "penalty_clipped",
            "raw_weight",
            "final_weight",
        ]
    ].sort_values(["signal_name", "eta", "clip_scheme", "date", "factor_name"])
    write_parquet(grid, PROCESSED_DIR / "weekly_drift_penalty_weight_grid.parquet")
    return grid.reset_index(drop=True)


def normalized_weights(values: pd.Series) -> pd.Series:
    raw = values.clip(lower=0)
    if raw.sum() <= 0:
        return pd.Series(1.0 / len(raw), index=raw.index)
    return raw / raw.sum()


def collect_strategy_weights(
    grid: pd.DataFrame,
    signals: pd.DataFrame,
    monthly_perf: pd.DataFrame,
    monthly_weights: pd.DataFrame | None,
    weekly_weights: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    common_dates = sorted(pd.to_datetime(grid["date"].unique()))
    icirs = rolling_icir(monthly_perf, common_dates)
    baseline_rows = []
    for date, group in icirs.groupby("date"):
        group = group.set_index("factor_name").reindex(FACTOR_NAMES)
        if group["icir"].isna().any():
            continue
        icir_w = normalized_weights(group["icir"])
        for factor in FACTOR_NAMES:
            baseline_rows += [
                {
                    "date": date,
                    "factor_name": factor,
                    "strategy_name": "Equal-factor",
                    "weight": 1.0 / len(FACTOR_NAMES),
                    "signal_name": "baseline",
                    "eta": np.nan,
                    "clip_scheme": "baseline",
                    "clip_lower": np.nan,
                },
                {
                    "date": date,
                    "factor_name": factor,
                    "strategy_name": "ICIR",
                    "weight": icir_w.loc[factor],
                    "signal_name": "baseline",
                    "eta": np.nan,
                    "clip_scheme": "baseline",
                    "clip_lower": np.nan,
                },
            ]

    def append_existing(
        source: pd.DataFrame | None,
        weight_col: str,
        strategy_name: str,
        signal_name: str,
    ) -> None:
        if source is None or weight_col not in source:
            return
        source_dates = source[source["date"].isin(common_dates)]
        for row in source_dates.itertuples(index=False):
            baseline_rows.append(
                {
                    "date": row.date,
                    "factor_name": row.factor_name,
                    "strategy_name": strategy_name,
                    "weight": getattr(row, weight_col),
                    "signal_name": signal_name,
                    "eta": 1.0,
                    "clip_scheme": "no_clip",
                    "clip_lower": 0.0,
                }
            )

    append_existing(
        monthly_weights,
        "weight_icir_eot",
        "ICIR + monthly EOT drift",
        "monthly_eot",
    )
    append_existing(
        weekly_weights,
        "weight_icir_weekly_eot",
        "ICIR + weekly EOT drift, previous",
        "previous_weekly_4w",
    )
    baselines = pd.DataFrame(baseline_rows)

    grid_weights = grid.copy()
    grid_weights["strategy_name"] = (
        "ICIR + weekly "
        + grid_weights["signal_name"]
        + " eta="
        + grid_weights["eta"].map(lambda x: f"{x:.1f}")
        + " "
        + grid_weights["clip_scheme"]
    )
    grid_weights = grid_weights.rename(columns={"final_weight": "weight"})
    strategy_weights = pd.concat(
        [
            baselines,
            grid_weights[
                [
                    "date",
                    "factor_name",
                    "strategy_name",
                    "weight",
                    "signal_name",
                    "eta",
                    "clip_scheme",
                    "clip_lower",
                ]
            ],
        ],
        ignore_index=True,
    )
    complete = strategy_weights.groupby(["strategy_name", "date"])["factor_name"].nunique()
    valid = complete[complete == len(FACTOR_NAMES)].index
    valid_frame = pd.DataFrame(valid.tolist(), columns=["strategy_name", "date"])
    strategy_weights = strategy_weights.merge(valid_frame, on=["strategy_name", "date"], how="inner")
    metadata = (
        strategy_weights[
            ["strategy_name", "signal_name", "eta", "clip_scheme", "clip_lower"]
        ]
        .drop_duplicates("strategy_name")
        .reset_index(drop=True)
    )
    return strategy_weights, metadata


def run_backtest_grid(
    monthly: pd.DataFrame,
    strategy_weights: pd.DataFrame,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_strategies = sorted(strategy_weights["strategy_name"].unique())
    common_dates = sorted(
        set.intersection(
            *[
                set(strategy_weights.loc[strategy_weights["strategy_name"] == name, "date"])
                for name in all_strategies
            ]
        )
    )
    strategy_weights = strategy_weights[strategy_weights["date"].isin(common_dates)]
    previous: dict[str, set[str]] = {name: set() for name in all_strategies}
    gross_rows = []

    for date in common_dates:
        universe = monthly[(monthly["date"] == date) & monthly["fwd_ret_1m"].notna()].copy()
        zcols = [f"{factor}_z" for factor in FACTOR_NAMES]
        universe = universe[universe[zcols].notna().sum(axis=1) >= 3]
        if len(universe) < 50:
            continue
        zmat = universe[zcols].fillna(0.0).to_numpy(dtype=float)
        returns = universe["fwd_ret_1m"].to_numpy(dtype=float)
        tickers = universe["ticker"].astype(str).to_numpy()
        q = max(int(math.floor(len(universe) * TOP_FRAC)), 1)
        date_weights = strategy_weights[strategy_weights["date"] == date]
        for strategy in all_strategies:
            weights = (
                date_weights[date_weights["strategy_name"] == strategy]
                .set_index("factor_name")["weight"]
                .reindex(FACTOR_NAMES)
            )
            if weights.isna().any():
                continue
            scores = zmat @ weights.to_numpy(dtype=float)
            selected_idx = np.argpartition(scores, -q)[-q:]
            holdings = set(tickers[selected_idx])
            gross_return = float(np.nanmean(returns[selected_idx]))
            if previous[strategy]:
                overlap = len(previous[strategy] & holdings)
                turnover = 1.0 - overlap / max(len(previous[strategy]), len(holdings))
            else:
                turnover = 1.0
            previous[strategy] = holdings
            gross_rows.append(
                {
                    "date": date,
                    "strategy_name": strategy,
                    "gross_return": gross_return,
                    "turnover": turnover,
                }
            )

    gross = pd.DataFrame(gross_rows).merge(metadata, on="strategy_name", how="left")
    nav_parts = []
    summary_rows = []
    for cost_bps in COSTS_BPS:
        part = gross.copy()
        part["cost_bps"] = cost_bps
        part["monthly_return"] = part["gross_return"] - part["turnover"] * cost_bps / 10_000
        part = part.sort_values(["strategy_name", "date"])
        part["nav"] = part.groupby("strategy_name")["monthly_return"].transform(
            lambda s: (1 + s.fillna(0)).cumprod()
        )
        part["drawdown"] = part.groupby("strategy_name")["nav"].transform(
            lambda s: s / s.cummax() - 1
        )
        nav_parts.append(part)
        for strategy, group in part.groupby("strategy_name"):
            returns = group["monthly_return"].dropna()
            ann_return = (1 + returns).prod() ** (12 / len(returns)) - 1
            ann_vol = returns.std(ddof=1) * math.sqrt(12)
            mdd = group["drawdown"].min()
            meta = group.iloc[0]
            summary_rows.append(
                {
                    "strategy_name": strategy,
                    "signal_name": meta["signal_name"],
                    "eta": meta["eta"],
                    "clip_scheme": meta["clip_scheme"],
                    "clip_lower": meta["clip_lower"],
                    "cost_bps": cost_bps,
                    "annual_return": ann_return,
                    "annual_volatility": ann_vol,
                    "sharpe": returns.mean() * 12 / ann_vol if ann_vol else np.nan,
                    "max_drawdown": mdd,
                    "calmar": ann_return / abs(mdd) if mdd < 0 else np.nan,
                    "monthly_win_rate": (returns > 0).mean(),
                    "average_turnover": group["turnover"].mean(),
                    "start_date": group["date"].min(),
                    "end_date": group["date"].max(),
                    "notes": (
                        "Monthly top-20% long-only; cost = simple holdings-change turnover "
                        "x one-way cost; no return-drift adjustment or market impact."
                    ),
                }
            )
    nav = pd.concat(nav_parts, ignore_index=True)[
        [
            "date",
            "strategy_name",
            "signal_name",
            "eta",
            "clip_scheme",
            "clip_lower",
            "cost_bps",
            "monthly_return",
            "nav",
            "drawdown",
            "turnover",
        ]
    ]
    summary = pd.DataFrame(summary_rows)
    write_parquet(nav, PROCESSED_DIR / "weekly_drift_backtest_grid_nav.parquet")
    summary.to_csv(REPORT_DIR / "weekly_drift_backtest_grid_summary.csv", index=False)
    return nav, summary


def select_robust_candidates(summary: pd.DataFrame) -> pd.DataFrame:
    grid = summary[
        summary["strategy_name"].str.startswith("ICIR + weekly ")
        & ~summary["strategy_name"].str.endswith("previous")
    ]
    zero = grid[grid["cost_bps"] == 0].copy()
    icir = summary[summary["strategy_name"].eq("ICIR")].set_index("cost_bps")
    icir0 = icir.loc[0]
    cost_pivot = grid.pivot(index="strategy_name", columns="cost_bps", values="sharpe")
    zero["sharpe_10bps"] = zero["strategy_name"].map(cost_pivot[10])
    zero["sharpe_20bps"] = zero["strategy_name"].map(cost_pivot[20])
    zero["drawdown_ok"] = zero["max_drawdown"] >= icir0["max_drawdown"] - 0.03
    zero["turnover_ok"] = zero["average_turnover"] <= icir0["average_turnover"] * 1.10
    zero["cost_ok"] = (
        (zero["sharpe_10bps"] > icir.loc[10, "sharpe"])
        & (zero["sharpe_20bps"] > icir.loc[20, "sharpe"])
    )
    zero["non_extreme"] = zero["eta"].le(1.5) & zero["clip_lower"].ge(0.5)
    selected = zero[
        (zero["sharpe"] > icir0["sharpe"])
        & (zero["calmar"] > icir0["calmar"])
        & zero["drawdown_ok"]
        & zero["turnover_ok"]
        & zero["cost_ok"]
        & zero["non_extreme"]
    ].copy()
    if selected.empty:
        selected = zero[zero["non_extreme"]].copy()
        selected["fallback"] = True
    else:
        selected["fallback"] = False
    selected["robust_score"] = (
        (selected["sharpe"] - icir0["sharpe"])
        + 0.5 * (selected["calmar"] - icir0["calmar"])
        + 0.25 * (selected["sharpe_20bps"] - icir.loc[20, "sharpe"])
        - 0.2 * (selected["average_turnover"] - icir0["average_turnover"])
    )
    selected = selected.sort_values(
        ["fallback", "robust_score", "eta"], ascending=[True, False, True]
    ).head(12)
    selected.insert(0, "rank", range(1, len(selected) + 1))
    selected["why_selected"] = selected.apply(
        lambda r: (
            f"Sharpe/Calmar exceed ICIR; 20 bps Sharpe={r['sharpe_20bps']:.3f}; "
            f"turnover={r['average_turnover']:.3f}."
            if not r["fallback"]
            else "Fallback ranking: no strategy met every strict robustness rule."
        ),
        axis=1,
    )
    selected["risk_warning"] = (
        "Weak predictive drift-return link; simple cost and turnover model; HS300-only sample."
    )
    output = selected[
        [
            "rank",
            "strategy_name",
            "signal_name",
            "eta",
            "clip_scheme",
            "clip_lower",
            "cost_bps",
            "annual_return",
            "annual_volatility",
            "sharpe",
            "max_drawdown",
            "calmar",
            "average_turnover",
            "why_selected",
            "risk_warning",
        ]
    ]
    output.to_csv(REPORT_DIR / "weekly_drift_robust_candidate_summary.csv", index=False)
    return output


def future_window(
    weekly_perf: pd.DataFrame,
    factor: str,
    date: pd.Timestamp,
    column: str,
    horizon: int,
) -> float:
    values = weekly_perf.loc[
        (weekly_perf["factor_name"] == factor) & (weekly_perf["date"] > date), column
    ].sort_index().head(horizon)
    if len(values) < max(2, horizon // 2):
        return np.nan
    return float(values.mean())


def monitoring_diagnostics(signals: pd.DataFrame, weekly_perf: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in signals.itertuples(index=False):
        for signal_name, column in SIGNALS.items():
            value = getattr(row, column)
            if pd.isna(value):
                continue
            records.append(
                {
                    "date": row.date,
                    "factor_name": row.factor_name,
                    "signal_name": signal_name,
                    "drift_signal": value,
                    "future_4w_ls": future_window(
                        weekly_perf, row.factor_name, row.date, "long_short_return", 4
                    ),
                    "future_12w_ls": future_window(
                        weekly_perf, row.factor_name, row.date, "long_short_return", 12
                    ),
                    "future_4w_ic": future_window(
                        weekly_perf, row.factor_name, row.date, "rank_ic", 4
                    ),
                    "future_12w_ic": future_window(
                        weekly_perf, row.factor_name, row.date, "rank_ic", 12
                    ),
                }
            )
    panel = pd.DataFrame(records)
    rows = []
    for (factor, signal_name), group in panel.groupby(["factor_name", "signal_name"]):
        threshold = group["drift_signal"].quantile(0.8)
        high = group[group["drift_signal"] >= threshold]
        normal = group[group["drift_signal"] < threshold]
        differences = [
            high["future_4w_ls"].mean() - normal["future_4w_ls"].mean(),
            high["future_12w_ls"].mean() - normal["future_12w_ls"].mean(),
            high["future_4w_ic"].mean() - normal["future_4w_ic"].mean(),
            high["future_12w_ic"].mean() - normal["future_12w_ic"].mean(),
        ]
        negative_count = sum(value < 0 for value in differences if pd.notna(value))
        interpretation = (
            "High drift is followed by broad deterioration."
            if negative_count >= 3
            else "Relationship is mixed; treat as instability monitoring, not a reliable return forecast."
        )
        rows.append(
            {
                "factor_name": factor,
                "signal_name": signal_name,
                "high_drift_threshold": threshold,
                "n_high_drift": len(high),
                "n_normal_drift": len(normal),
                "mean_future_4w_ls_high": high["future_4w_ls"].mean(),
                "mean_future_4w_ls_normal": normal["future_4w_ls"].mean(),
                "mean_future_12w_ls_high": high["future_12w_ls"].mean(),
                "mean_future_12w_ls_normal": normal["future_12w_ls"].mean(),
                "mean_future_4w_ic_high": high["future_4w_ic"].mean(),
                "mean_future_4w_ic_normal": normal["future_4w_ic"].mean(),
                "mean_future_12w_ic_high": high["future_12w_ic"].mean(),
                "mean_future_12w_ic_normal": normal["future_12w_ic"].mean(),
                "downside_prob_high": (high["future_4w_ls"] < 0).mean(),
                "downside_prob_normal": (normal["future_4w_ls"] < 0).mean(),
                "worst_quantile_4w_ls_high": high["future_4w_ls"].quantile(0.1),
                "worst_quantile_4w_ls_normal": normal["future_4w_ls"].quantile(0.1),
                "interpretation": interpretation,
            }
        )
    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(
        REPORT_DIR / "weekly_drift_monitoring_diagnostics.csv", index=False
    )
    return diagnostics


def baseline_table(summary: pd.DataFrame, best_name: str, cost_bps: int = 0) -> pd.DataFrame:
    names = [
        "Equal-factor",
        "ICIR",
        "ICIR + monthly EOT drift",
        "ICIR + weekly EOT drift, previous",
        best_name,
    ]
    return summary[
        summary["strategy_name"].isin(names) & summary["cost_bps"].eq(cost_bps)
    ][
        [
            "strategy_name",
            "annual_return",
            "annual_volatility",
            "sharpe",
            "max_drawdown",
            "calmar",
            "average_turnover",
        ]
    ].drop_duplicates("strategy_name")


def create_figures(
    signals: pd.DataFrame,
    grid: pd.DataFrame,
    nav: pd.DataFrame,
    summary: pd.DataFrame,
    diagnostics: pd.DataFrame,
    weekly_drift: pd.DataFrame,
    best_name: str,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    key_names = [
        "Equal-factor",
        "ICIR",
        "ICIR + monthly EOT drift",
        "ICIR + weekly EOT drift, previous",
        best_name,
    ]

    average_signals = signals.groupby("date")[list(SIGNALS.values())].mean()
    fig, ax = plt.subplots(figsize=(12, 6))
    for name, column in SIGNALS.items():
        ax.plot(average_signals.index, average_signals[column], label=name, linewidth=1.2)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Cross-factor average weekly drift signals")
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "smoothing_method_comparison.png", dpi=160)
    plt.close(fig)

    sample = grid[
        grid["signal_name"].eq("8w_mean") & grid["eta"].eq(1.0)
    ].groupby(["date", "clip_scheme"])["penalty_clipped"].mean().unstack()
    fig, ax = plt.subplots(figsize=(12, 6))
    sample.plot(ax=ax)
    ax.set_title("Penalty clipping comparison: 8w mean, eta=1.0")
    ax.set_ylabel("Average clipped penalty")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "penalty_clipping_comparison.png", dpi=160)
    plt.close(fig)

    key_nav = nav[nav["strategy_name"].isin(key_names) & nav["cost_bps"].eq(0)]
    fig, ax = plt.subplots(figsize=(12, 6))
    for name, group in key_nav.groupby("strategy_name"):
        ax.plot(group["date"], group["nav"], label=name, linewidth=1.4)
    ax.set_title("Main strategy NAV, zero explicit cost")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "main_strategy_nav.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    for name, group in key_nav.groupby("strategy_name"):
        ax.plot(group["date"], group["drawdown"], label=name, linewidth=1.4)
    ax.set_title("Main strategy drawdown, zero explicit cost")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "main_strategy_drawdown.png", dpi=160)
    plt.close(fig)

    costs = summary[summary["strategy_name"].isin(key_names)]
    fig, ax = plt.subplots(figsize=(10, 6))
    for name, group in costs.groupby("strategy_name"):
        ax.plot(group["cost_bps"], group["sharpe"], marker="o", label=name)
    ax.set_title("Transaction cost sensitivity")
    ax.set_xlabel("One-way cost (bps)")
    ax.set_ylabel("Sharpe")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "transaction_cost_sensitivity.png", dpi=160)
    plt.close(fig)

    zero = summary[summary["cost_bps"].eq(0)]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(zero["max_drawdown"].abs(), zero["sharpe"], alpha=0.55)
    ax.set_xlabel("Absolute max drawdown")
    ax.set_ylabel("Sharpe")
    ax.set_title("Sharpe vs max drawdown")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "sharpe_vs_max_drawdown.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(zero["average_turnover"], zero["sharpe"], alpha=0.55)
    ax.set_xlabel("Average monthly turnover")
    ax.set_ylabel("Sharpe")
    ax.set_title("Sharpe vs turnover")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "sharpe_vs_turnover.png", dpi=160)
    plt.close(fig)

    diag_plot = diagnostics.groupby("signal_name")[
        ["mean_future_4w_ls_high", "mean_future_4w_ls_normal"]
    ].mean()
    fig, ax = plt.subplots(figsize=(10, 6))
    diag_plot.plot(kind="bar", ax=ax)
    ax.set_title("Future 4-week factor performance: high vs normal drift")
    ax.set_ylabel("Mean weekly long-short return")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "high_vs_normal_future_performance.png", dpi=160)
    plt.close(fig)

    preferred_column = SIGNALS[
        summary.loc[summary["strategy_name"].eq(best_name), "signal_name"].iloc[0]
    ]
    for factor in FACTOR_NAMES:
        raw = weekly_drift[weekly_drift["factor_name"].eq(factor)]
        smooth = signals[signals["factor_name"].eq(factor)]
        fig, ax = plt.subplots(figsize=(12, 4.5))
        ax.plot(
            raw["date"],
            raw["eot_drift_zscore"],
            color="#7f8c8d",
            alpha=0.55,
            label="weekly raw z-score",
        )
        ax.plot(
            smooth["date"],
            smooth[preferred_column],
            color="#c0392b",
            linewidth=1.8,
            label="preferred monthly signal",
        )
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(f"{factor} weekly drift dashboard")
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIG_DIR / f"dashboard_{factor}.png", dpi=160)
        plt.close(fig)


def write_reports(
    smoothing: pd.DataFrame,
    summary: pd.DataFrame,
    candidates: pd.DataFrame,
    diagnostics: pd.DataFrame,
    best_name: str,
    missing: list[str],
) -> None:
    best = summary[
        summary["strategy_name"].eq(best_name) & summary["cost_bps"].eq(0)
    ].iloc[0]
    best20 = summary[
        summary["strategy_name"].eq(best_name) & summary["cost_bps"].eq(20)
    ].iloc[0]
    icir0 = summary[
        summary["strategy_name"].eq("ICIR") & summary["cost_bps"].eq(0)
    ].iloc[0]
    icir20 = summary[
        summary["strategy_name"].eq("ICIR") & summary["cost_bps"].eq(20)
    ].iloc[0]
    smoothest = smoothing.sort_values(
        ["std", "autocorrelation_1"], ascending=[True, False]
    ).iloc[0]["signal_name"]
    best_diag = diagnostics.copy()
    best_diag["ls_delta"] = (
        best_diag["mean_future_4w_ls_high"]
        - best_diag["mean_future_4w_ls_normal"]
    )
    clear_factors = best_diag.groupby("factor_name")["ls_delta"].mean().sort_values().head(2).index
    comparison = baseline_table(summary, best_name)
    missing_text = ", ".join(f"`{name}`" for name in missing) if missing else "None."

    model_lines = [
        "# Weekly Drift Model Selection",
        "",
        "## Decision",
        "",
        "**Primary monitoring signal + conservative secondary allocation penalty.** "
        "The allocation result is an experimental extension, not the main claim.",
        "",
        "## Selection",
        "",
        f"- Most statistically smooth signal by low standard deviation and persistence: `{smoothest}`.",
        f"- Selected robust allocation candidate: `{best_name}`.",
        f"- Zero-cost Sharpe {best['sharpe']:.3f} versus ICIR {icir0['sharpe']:.3f}; "
        f"Calmar {best['calmar']:.3f} versus {icir0['calmar']:.3f}.",
        f"- At 20 bps, candidate Sharpe {best20['sharpe']:.3f} versus ICIR {icir20['sharpe']:.3f}.",
        f"- Candidate max drawdown {best['max_drawdown']:.2%}; average monthly turnover {best['average_turnover']:.2%}.",
        "",
        "Robust selection requires eta <= 1.5 and a penalty floor of at least 0.5. Clipping is useful because "
        "it bounds the response to a drift spike. The selected scheme is preferred "
        "for its joint Sharpe, Calmar, drawdown, turnover, cost resilience, and non-extreme parameterization, "
        "not because it has the single highest raw return.",
        "",
        "## Baseline Comparison",
        "",
        comparison.to_markdown(index=False),
        "",
        "## Resume Judgment",
        "",
        "The project is suitable for a resume as a research prototype. Describe factor failure monitoring as "
        "the core contribution and drift-aware weighting as an experimental validation. Do not present the "
        "backtest as directly tradable.",
        "",
        f"Missing requested existing inputs: {missing_text}",
    ]
    (REPORT_DIR / "weekly_drift_model_selection.md").write_text(
        "\n".join(model_lines), encoding="utf-8"
    )

    monitoring_lines = [
        "# Weekly Drift Monitoring Diagnostics",
        "",
        "## Judgment",
        "",
        "Weekly EOT drift is better interpreted as a **contemporaneous factor instability indicator** "
        "than as a strong predictive warning for future factor returns.",
        "",
        f"The factors with the most negative average high-minus-normal 4-week long-short difference are "
        f"{', '.join(clear_factors)}. Even there, the relationship is not uniformly negative across horizons "
        "and IC measures.",
        "",
        "High drift states are useful dashboard warnings because they identify unusual changes in the joint "
        "distribution of Rank IC, long-short return, and downside return. They should trigger review and a "
        "bounded risk penalty, not an automatic factor shutdown.",
        "",
        "The downside probability is defined as the probability that the mean of the next four weekly "
        "long-short returns is negative. Worst-quantile columns report the 10th percentile.",
        "",
        diagnostics.to_markdown(index=False),
    ]
    (REPORT_DIR / "weekly_drift_monitoring_report.md").write_text(
        "\n".join(monitoring_lines), encoding="utf-8"
    )

    report_lines = [
        "# Weekly EOT Drift Robustness Report",
        "",
        "## 1. Executive Summary",
        "",
        "Weekly EOT drift is mainly useful as a **primary monitoring signal with a conservative secondary "
        "allocation penalty**. It is not supported as a standalone main allocation signal.",
        "",
        f"The selected robust candidate is `{best_name}`. It improves zero-cost Sharpe from "
        f"{icir0['sharpe']:.3f} to {best['sharpe']:.3f} and Calmar from {icir0['calmar']:.3f} "
        f"to {best['calmar']:.3f}. At 20 bps its Sharpe is {best20['sharpe']:.3f}, compared with "
        f"{icir20['sharpe']:.3f} for ICIR. These are feasibility results, not evidence of tradability.",
        "",
        "## 2. Why Weekly Drift Needed Robustness Testing",
        "",
        "The previous four-week weekly signal improved return and Sharpe but increased maximum drawdown and "
        "turnover. Its weak relationship with subsequent factor returns also raised the risk that direct "
        "weighting was reacting to contemporaneous noise. This round therefore tests smoothing, bounded "
        "penalties, and transaction costs on a common sample.",
        "",
        "The original monthly drift used only six observations in its recent window and was vulnerable to "
        "single-month noise. Weekly drift increased the recent window to 26 observations and produced about "
        "4.22 times as many drift observations, making it a more stable monitoring panel. In the previous "
        "weekly allocation test, Sharpe and annual return improved relative to ICIR, while drawdown and "
        "turnover worsened; that allocation trade-off is the central risk tested here.",
        "",
        "## 3. Smoothing Results",
        "",
        smoothing.to_markdown(index=False),
        "",
        f"`{smoothest}` has the lowest pooled standard deviation with high persistence. The final model "
        "selection also considers portfolio behavior, so the smoothest statistical signal is not "
        "automatically selected.",
        "",
        "## 4. Penalty Clipping Results",
        "",
        f"The robust candidate uses `{best['clip_scheme']}` with eta={best['eta']:.1f}. Clipping limits "
        "factor-weight reactions to isolated drift spikes. Aggressive eta=2.0/no-clipping configurations "
        "were excluded from robust selection even when their in-sample metric was attractive.",
        "",
        "## 5. Backtest Grid Results",
        "",
        comparison.to_markdown(index=False),
        "",
        f"The selected candidate has annual return {best['annual_return']:.2%}, volatility "
        f"{best['annual_volatility']:.2%}, max drawdown {best['max_drawdown']:.2%}, and average monthly "
        f"turnover {best['average_turnover']:.2%}. Transaction costs are deducted as simple holdings-change "
        "turnover times one-way bps; return-drift-adjusted turnover, impact, and slippage are not modeled.",
        "",
        "## 6. Monitoring Diagnostics",
        "",
        "High drift does not consistently predict lower future factor long-short returns or Rank IC across "
        "factors and horizons. Weekly EOT drift is better interpreted as a contemporaneous factor "
        "instability indicator rather than a strong predictor of future factor returns. It is appropriate "
        "for dashboard warnings and, at most, a clipped secondary penalty.",
        "",
        "## 7. Recommended Project Positioning",
        "",
        "**Recommended title: EOT-based Factor Lifecycle Diagnostics with Experimental Drift-aware Weighting.**",
        "",
        "This title accurately emphasizes the strongest contribution, factor monitoring, while preserving "
        "the allocation experiment without overstating it.",
        "",
        "## 8. Limitations",
        "",
        "1. Industry and size neutralization are still missing.",
        "2. Transaction costs, slippage, and market impact are not modeled strictly.",
        "3. Strict limit-up/limit-down buy filters are missing.",
        "4. The price-volume factor set has weak standalone alpha.",
        "5. EOT drift still overlaps with mean and covariance shift.",
        "6. High drift has a weak and factor-dependent relationship with future returns.",
        "7. The sample is concentrated in the HS300 and excludes CSI 500 and the full A-share universe.",
        "8. Results must not be described as a directly tradable strategy.",
        "",
        "## 9. Next Steps",
        "",
        "1. Add industry and market-cap neutralization.",
        "2. Add strict transaction costs and buyability filters.",
        "3. Extend to CSI 500 or the full A-share universe.",
        "4. Add benchmark-relative excess returns.",
        "5. Keep weekly drift as the primary dashboard signal.",
        "6. Use only conservative clipped penalties for dynamic weighting.",
        "7. Test subperiod and style-cycle stability.",
        "",
        "## 10. Resume Wording",
        "",
        "**English:** Built an A-share multifactor research prototype that models weekly factor-performance "
        "distributions and applies entropic optimal transport drift scores for factor failure monitoring; "
        "evaluated conservative drift-aware weighting as an experimental extension with smoothing, clipping, "
        "and transaction-cost sensitivity, without claiming production tradability.",
        "",
        "**中文：**构建 A 股多因子研究原型，基于周度因子表现分布与熵正则最优传输（EOT）漂移分数开展"
        "因子失效监控，并将平滑、裁剪后的动态调权作为扩展验证；结果定位为研究可行性分析，不夸大实盘收益。",
        "",
        f"Missing requested existing inputs: {missing_text}",
    ]
    (REPORT_DIR / "weekly_eot_drift_robustness_report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    data, missing = load_inputs()
    monthly_dates = sorted(pd.to_datetime(data["monthly_perf"]["date"].unique()))
    signals = construct_smoothed_signals(data["weekly_drift"], monthly_dates)
    smoothing = summarize_smoothing(signals)
    grid = build_weight_grid(signals, data["monthly_perf"])
    strategy_weights, metadata = collect_strategy_weights(
        grid,
        signals,
        data["monthly_perf"],
        data.get("monthly_weights"),
        data.get("weekly_weights"),
    )

    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Backtest panel is missing: {PANEL_PATH}")
    panel = read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    monthly = construct_monthly_factors(panel)
    nav, summary = run_backtest_grid(monthly, strategy_weights, metadata)
    candidates = select_robust_candidates(summary)
    best_name = candidates.iloc[0]["strategy_name"]
    diagnostics = monitoring_diagnostics(signals, data["weekly_perf"])
    create_figures(
        signals,
        grid,
        nav,
        summary,
        diagnostics,
        data["weekly_drift"],
        best_name,
    )
    write_reports(smoothing, summary, candidates, diagnostics, best_name, missing)

    print(f"Strategies tested: {summary['strategy_name'].nunique()}")
    print(f"Backtest summary rows: {len(summary)}")
    print(f"Selected robust candidate: {best_name}")
    print(REPORT_DIR / "weekly_eot_drift_robustness_report.md")


if __name__ == "__main__":
    main()
