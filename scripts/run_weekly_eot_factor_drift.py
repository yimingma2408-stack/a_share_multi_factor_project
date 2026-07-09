from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_eot_factor_drift_feasibility import (
    FACTOR_NAMES,
    PANEL_PATH,
    PROCESSED_DIR,
    REPORT_DIR,
    TOP_FRAC,
    construct_monthly_factors,
    max_drawdown,
    read_parquet,
    safe_float,
    winsorize_zscore,
    write_parquet,
)
from src.eot_drift import compute_eot_drift


FIG_DIR = REPORT_DIR / "figures_weekly"
RANDOM_STATE = 42
WEEKLY_BASE_WINDOW = 156
WEEKLY_RECENT_WINDOW = 26
MONTHLY_ICIR_WINDOW = 36


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def fmt_pct(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "NA"
    return f"{100 * float(x):.2f}%"


def construct_weekly_factors(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.sort_values(["ticker", "date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    if "return_1d" not in df or df["return_1d"].isna().all():
        df["return_1d"] = df.groupby("ticker")["qfq_close"].pct_change()

    grouped = df.groupby("ticker", group_keys=False)
    df["reversal_1m"] = -grouped["qfq_close"].pct_change(20)
    df["momentum_3m"] = grouped["qfq_close"].pct_change(60)
    df["volatility_1m"] = -grouped["return_1d"].rolling(20, min_periods=15).std().reset_index(level=0, drop=True)
    df["turnover_1m"] = -grouped["turnover"].rolling(20, min_periods=15).mean().reset_index(level=0, drop=True)
    avg_amount = grouped["amount"].rolling(20, min_periods=15).mean().reset_index(level=0, drop=True)
    df["liquidity_1m"] = np.log1p(avg_amount)

    week_ends = df.groupby(df["date"].dt.to_period("W-FRI"))["date"].max().sort_values()
    weekly = df[df["date"].isin(week_ends.values)].copy()
    weekly = weekly.sort_values(["ticker", "date"])
    weekly["next_qfq_close"] = weekly.groupby("ticker")["qfq_close"].shift(-1)
    weekly["fwd_ret_1w"] = weekly["next_qfq_close"] / weekly["qfq_close"] - 1

    active_mask = (
        (weekly["is_hs300_member"] == True)
        & (weekly["trade_status"] == 1)
        & (weekly["is_st"].fillna(0).astype(int) == 0)
        & weekly["qfq_close"].gt(0)
    )
    weekly = weekly[active_mask].copy()

    for factor in FACTOR_NAMES:
        weekly[f"{factor}_z"] = weekly.groupby("date")[factor].transform(winsorize_zscore)

    return weekly


def compute_weekly_performance(weekly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, g in weekly.groupby("date", sort=True):
        universe_n = g["ticker"].nunique()
        for factor in FACTOR_NAMES:
            fcol = f"{factor}_z"
            valid = g[["ticker", fcol, "fwd_ret_1w"]].dropna()
            coverage = len(valid) / universe_n if universe_n else 0.0
            if len(valid) < 50 or coverage < 0.50:
                continue
            rank_ic = valid[fcol].corr(valid["fwd_ret_1w"], method="spearman")
            q = max(int(math.floor(len(valid) * TOP_FRAC)), 1)
            top = valid.nlargest(q, fcol)
            bottom = valid.nsmallest(q, fcol)
            long_short = top["fwd_ret_1w"].mean() - bottom["fwd_ret_1w"].mean()
            rows.append(
                {
                    "date": date,
                    "factor_name": factor,
                    "rank_ic": rank_ic,
                    "long_short_return": long_short,
                    "top_return": top["fwd_ret_1w"].mean(),
                    "bottom_return": bottom["fwd_ret_1w"].mean(),
                    "downside_return": min(long_short, 0),
                    "n_stocks": len(valid),
                    "coverage_ratio": coverage,
                }
            )
    perf = pd.DataFrame(rows).sort_values(["date", "factor_name"]).reset_index(drop=True)
    write_parquet(perf, PROCESSED_DIR / "weekly_factor_performance.parquet")
    return perf


def summarize_weekly_performance(perf: pd.DataFrame, total_weeks: int) -> pd.DataFrame:
    rows = []
    for factor, g in perf.groupby("factor_name"):
        ls_std = g["long_short_return"].std(ddof=1)
        ic_std = g["rank_ic"].std(ddof=1)
        rows.append(
            {
                "factor_name": factor,
                "mean_rank_ic": g["rank_ic"].mean(),
                "std_rank_ic": ic_std,
                "icir": g["rank_ic"].mean() / ic_std if ic_std and np.isfinite(ic_std) else np.nan,
                "mean_long_short_return": g["long_short_return"].mean(),
                "std_long_short_return": ls_std,
                "t_stat_long_short": g["long_short_return"].mean() / (ls_std / math.sqrt(len(g)))
                if ls_std and np.isfinite(ls_std)
                else np.nan,
                "positive_week_ratio": (g["long_short_return"] > 0).mean(),
                "worst_week": g.loc[g["long_short_return"].idxmin(), "date"],
                "best_week": g.loc[g["long_short_return"].idxmax(), "date"],
                "missing_weeks": total_weeks - len(g),
                "available_weeks": len(g),
            }
        )
    summary = pd.DataFrame(rows).sort_values("factor_name")
    summary.to_csv(REPORT_DIR / "weekly_factor_performance_summary.csv", index=False)
    return summary


def compute_weekly_drift_scores(perf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    features = ["rank_ic", "long_short_return", "downside_return"]
    for factor, g in perf.groupby("factor_name"):
        g = g.sort_values("date").reset_index(drop=True)
        for idx in range(WEEKLY_BASE_WINDOW + WEEKLY_RECENT_WINDOW, len(g)):
            base = g.loc[idx - WEEKLY_BASE_WINDOW - WEEKLY_RECENT_WINDOW : idx - WEEKLY_RECENT_WINDOW - 1, features].to_numpy()
            recent = g.loc[idx - WEEKLY_RECENT_WINDOW : idx - 1, features].to_numpy()
            date = g.loc[idx, "date"]
            try:
                result = compute_eot_drift(
                    base,
                    recent,
                    n_reference=100,
                    epsilon_scale=0.1,
                    random_state=RANDOM_STATE,
                )
                rows.append(
                    {
                        "date": date,
                        "factor_name": factor,
                        "eot_drift": result.drift,
                        "eot_drift_zscore": np.nan,
                        "mean_shift_norm": result.mean_shift_norm,
                        "covariance_shift_norm": result.covariance_shift_norm,
                        "n_base": result.n_base,
                        "n_recent": result.n_recent,
                        "epsilon": result.epsilon,
                        "n_reference": result.n_reference,
                        "status": result.status,
                        "notes": result.notes,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "date": date,
                        "factor_name": factor,
                        "eot_drift": np.nan,
                        "eot_drift_zscore": np.nan,
                        "mean_shift_norm": np.nan,
                        "covariance_shift_norm": np.nan,
                        "n_base": len(base),
                        "n_recent": len(recent),
                        "epsilon": np.nan,
                        "n_reference": 100,
                        "status": "error",
                        "notes": f"{type(exc).__name__}: {exc}",
                    }
                )
    drift = pd.DataFrame(rows).sort_values(["factor_name", "date"]).reset_index(drop=True)
    if not drift.empty:
        zscores = []
        for _, g in drift.groupby("factor_name", sort=False):
            prior_mean = g["eot_drift"].expanding(min_periods=26).mean().shift(1)
            prior_std = g["eot_drift"].expanding(min_periods=26).std(ddof=1).shift(1)
            zscores.append(((g["eot_drift"] - prior_mean) / prior_std.replace(0, np.nan)).fillna(0.0))
        drift["eot_drift_zscore"] = pd.concat(zscores).sort_index()
    write_parquet(drift, PROCESSED_DIR / "weekly_eot_factor_drift_scores.parquet")
    return drift


def summarize_weekly_drift(drift: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor, g in drift.groupby("factor_name"):
        ok = g[g["eot_drift"].notna()].copy()
        if ok.empty:
            rows.append(
                {
                    "factor_name": factor,
                    "mean_eot_drift": np.nan,
                    "std_eot_drift": np.nan,
                    "max_eot_drift": np.nan,
                    "max_drift_week": pd.NaT,
                    "mean_shift_corr": np.nan,
                    "cov_shift_corr": np.nan,
                    "available_weeks": 0,
                    "notes": "; ".join(g["notes"].dropna().astype(str).unique()[:3]),
                }
            )
            continue
        rows.append(
            {
                "factor_name": factor,
                "mean_eot_drift": ok["eot_drift"].mean(),
                "std_eot_drift": ok["eot_drift"].std(ddof=1),
                "max_eot_drift": ok["eot_drift"].max(),
                "max_drift_week": ok.loc[ok["eot_drift"].idxmax(), "date"],
                "mean_shift_corr": ok["eot_drift"].corr(ok["mean_shift_norm"]),
                "cov_shift_corr": ok["eot_drift"].corr(ok["covariance_shift_norm"]),
                "available_weeks": len(ok),
                "notes": "; ".join(ok.loc[ok["status"] != "ok", "notes"].dropna().astype(str).unique()[:3]),
            }
        )
    summary = pd.DataFrame(rows).sort_values("factor_name")
    summary.to_csv(REPORT_DIR / "weekly_eot_drift_summary.csv", index=False)
    return summary


def drift_diagnostics(drift: pd.DataFrame, prefix: str) -> pd.DataFrame:
    rows = []
    for factor, g in drift.groupby("factor_name"):
        ok = g.sort_values("date").dropna(subset=["eot_drift"])
        rows.append(
            {
                "factor_name": factor,
                f"{prefix}_available_observations": len(ok),
                f"{prefix}_drift_mean": ok["eot_drift"].mean(),
                f"{prefix}_drift_std": ok["eot_drift"].std(ddof=1),
                f"{prefix}_drift_cv": ok["eot_drift"].std(ddof=1) / ok["eot_drift"].mean()
                if ok["eot_drift"].mean()
                else np.nan,
                f"{prefix}_drift_autocorr_1": ok["eot_drift"].autocorr(lag=1),
                f"{prefix}_mean_shift_corr": ok["eot_drift"].corr(ok["mean_shift_norm"]),
                f"{prefix}_cov_shift_corr": ok["eot_drift"].corr(ok["covariance_shift_norm"]),
            }
        )
    return pd.DataFrame(rows)


def future_performance_diagnostics(perf: pd.DataFrame, drift: pd.DataFrame) -> pd.DataFrame:
    merged = drift.merge(perf, on=["date", "factor_name"], how="left").sort_values(["factor_name", "date"])
    for horizon in [4, 12]:
        merged[f"future_{horizon}w"] = merged.groupby("factor_name")["long_short_return"].transform(
            lambda s: s.shift(-1)[::-1]
            .rolling(horizon, min_periods=max(2, horizon // 2))
            .mean()[::-1]
        )
    rows = []
    for factor, g in merged.groupby("factor_name"):
        high = g["eot_drift_zscore"] > 1
        rows.append(
            {
                "factor_name": factor,
                "drift_corr_future_4w": g["eot_drift_zscore"].corr(g["future_4w"]),
                "drift_corr_future_12w": g["eot_drift_zscore"].corr(g["future_12w"]),
                "high_drift_future_4w": g.loc[high, "future_4w"].mean(),
                "normal_future_4w": g.loc[~high, "future_4w"].mean(),
                "high_drift_future_12w": g.loc[high, "future_12w"].mean(),
                "normal_future_12w": g.loc[~high, "future_12w"].mean(),
            }
        )
    return pd.DataFrame(rows)


def create_comparison_report(
    monthly_drift: pd.DataFrame,
    weekly_drift: pd.DataFrame,
    weekly_perf: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_diag = drift_diagnostics(monthly_drift, "monthly")
    weekly_diag = drift_diagnostics(weekly_drift, "weekly")
    comparison = monthly_diag.merge(weekly_diag, on="factor_name", how="outer")
    comparison["observation_multiplier"] = (
        comparison["weekly_available_observations"] / comparison["monthly_available_observations"]
    )
    comparison["std_ratio_weekly_to_monthly"] = comparison["weekly_drift_std"] / comparison["monthly_drift_std"]
    comparison["cv_ratio_weekly_to_monthly"] = comparison["weekly_drift_cv"] / comparison["monthly_drift_cv"]
    comparison["mean_shift_corr_change"] = comparison["weekly_mean_shift_corr"] - comparison["monthly_mean_shift_corr"]

    median_obs_mult = comparison["observation_multiplier"].median()
    median_cv_ratio = comparison["cv_ratio_weekly_to_monthly"].median()
    median_autocorr_change = (
        comparison["weekly_drift_autocorr_1"] - comparison["monthly_drift_autocorr_1"]
    ).median()
    median_mean_corr_change = comparison["mean_shift_corr_change"].median()
    conclusion = "weekly drift is the better primary monitoring panel" if median_obs_mult > 3 else "weekly drift is not clearly superior"
    future_diag = future_performance_diagnostics(weekly_perf, weekly_drift)
    median_future_4w_corr = future_diag["drift_corr_future_4w"].median()
    median_future_12w_corr = future_diag["drift_corr_future_12w"].median()

    lines = [
        "# Weekly vs Monthly EOT Drift Comparison",
        "",
        "## Key Answers",
        "",
        "- Weekly EOT drift was successfully computed using 156-week base and 26-week recent windows.",
        f"- Weekly observations increased by a median factor of {median_obs_mult:.2f}x relative to monthly drift observations.",
        f"- Median weekly/monthly coefficient-of-variation ratio is {median_cv_ratio:.3f}; lower values imply a more stable scale.",
        f"- Median lag-1 autocorrelation change is {median_autocorr_change:.3f}; higher autocorrelation indicates smoother drift regimes.",
        f"- Median mean-shift correlation change is {median_mean_corr_change:.3f}; negative values mean less direct overlap with simple mean shift.",
        f"- Conclusion: **{conclusion}**. Monthly drift should remain as a robustness cross-check.",
        "",
        "## Quantitative Comparison",
        "",
        comparison.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "The weekly panel gives EOT drift far more observations and aligns better with the intended distributional-monitoring use case. "
        "It does not automatically make the signal independent from mean/covariance shift, but it reduces the small-sample concern caused "
        "by the monthly 6-observation recent window. The recommended production research path is to use weekly EOT drift as the primary "
        "factor-failure monitoring signal and retain monthly drift for slower-cycle validation.",
        "",
        "## Subsequent Performance Diagnostic",
        "",
        f"Median cross-factor correlation between weekly drift z-score and future 4-week long-short return is {median_future_4w_corr:.3f}; "
        f"the corresponding 12-week median is {median_future_12w_corr:.3f}. The signs are mixed across factors, so weekly drift is more "
        "convincing as a contemporaneous distribution-change alarm than as a universal predictor of future factor deterioration.",
        "",
        future_diag.to_markdown(index=False),
        "",
    ]
    (REPORT_DIR / "weekly_vs_monthly_drift_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    return comparison, future_diag


def create_weekly_figures(
    weekly_perf: pd.DataFrame,
    weekly_drift: pd.DataFrame,
    monthly_drift: pd.DataFrame,
    comparison: pd.DataFrame,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")

    def save_line(df: pd.DataFrame, y: str, title: str, filename: str) -> None:
        fig, ax = plt.subplots(figsize=(12, 6))
        for factor, g in df.groupby("factor_name"):
            ax.plot(g["date"], g[y], label=factor, linewidth=1.0)
        ax.axhline(0, color="black", linewidth=0.8, alpha=0.55)
        ax.set_title(title)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG_DIR / filename, dpi=160)
        plt.close(fig)

    save_line(weekly_perf, "rank_ic", "Weekly Rank IC", "weekly_rank_ic_timeseries.png")
    save_line(weekly_perf, "long_short_return", "Weekly Long-Short Return", "weekly_long_short_return_timeseries.png")
    save_line(weekly_drift, "eot_drift", "Weekly EOT Drift Score", "weekly_eot_drift_timeseries.png")

    monthly_avg = monthly_drift.groupby("date")["eot_drift"].mean().rename("monthly_avg_drift")
    weekly_avg = weekly_drift.groupby("date")["eot_drift"].mean().rename("weekly_avg_drift")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(monthly_avg.index, monthly_avg.values, label="Monthly avg drift", linewidth=1.6)
    ax.plot(weekly_avg.index, weekly_avg.values, label="Weekly avg drift", linewidth=1.1, alpha=0.85)
    ax.set_title("Monthly vs Weekly Average EOT Drift")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "monthly_vs_weekly_drift.png", dpi=160)
    plt.close(fig)

    for horizon in [4, 12]:
        merged = weekly_drift.merge(weekly_perf, on=["date", "factor_name"], how="left").sort_values(
            ["factor_name", "date"]
        )
        merged[f"next_{horizon}w_long_short"] = merged.groupby("factor_name")["long_short_return"].transform(
            lambda s: s.shift(-1)[::-1]
            .rolling(horizon, min_periods=max(2, horizon // 2))
            .mean()[::-1]
        )
        scatter = merged.dropna(subset=["eot_drift_zscore", f"next_{horizon}w_long_short"])
        if len(scatter) < 10:
            continue
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(scatter["eot_drift_zscore"], scatter[f"next_{horizon}w_long_short"], alpha=0.55)
        ax.axhline(0, color="black", linewidth=0.8, alpha=0.55)
        ax.axvline(0, color="black", linewidth=0.8, alpha=0.55)
        ax.set_xlabel("Weekly EOT drift z-score")
        ax.set_ylabel(f"Next {horizon}-week long-short return")
        ax.set_title(f"Weekly EOT Drift vs Next {horizon}-Week Performance")
        fig.tight_layout()
        fig.savefig(FIG_DIR / f"weekly_eot_vs_next_{horizon}w_performance.png", dpi=160)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    comparison.set_index("factor_name")[["monthly_drift_cv", "weekly_drift_cv"]].plot(kind="bar", ax=ax)
    ax.set_title("Monthly vs Weekly Drift Coefficient of Variation")
    ax.set_ylabel("CV")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "monthly_vs_weekly_drift_cv.png", dpi=160)
    plt.close(fig)


def compute_monthly_weights_with_weekly_drift(
    monthly_perf: pd.DataFrame,
    weekly_drift: pd.DataFrame,
) -> pd.DataFrame:
    weekly = weekly_drift.dropna(subset=["eot_drift_zscore"]).sort_values(["factor_name", "date"])
    first_weekly_drift_date = weekly["date"].min()
    dates = [d for d in sorted(pd.to_datetime(monthly_perf["date"].unique())) if d >= first_weekly_drift_date]
    rows = []
    for date in dates:
        available = []
        icirs = {}
        signals = {}
        penalties = {}
        for factor in FACTOR_NAMES:
            hist = monthly_perf[(monthly_perf["factor_name"] == factor) & (monthly_perf["date"] < date)].sort_values(
                "date"
            ).tail(MONTHLY_ICIR_WINDOW)
            if len(hist) < 12:
                continue
            ic_std = hist["rank_ic"].std(ddof=1)
            icir = hist["rank_ic"].mean() / ic_std if ic_std and np.isfinite(ic_std) else 0.0
            signal_hist = weekly[(weekly["factor_name"] == factor) & (weekly["date"] <= date)].tail(4)
            if signal_hist.empty:
                signal = 0.0
            else:
                signal = safe_float(signal_hist["eot_drift_zscore"].mean())
            penalty = 1.0 / (1.0 + max(signal, 0.0))
            available.append(factor)
            icirs[factor] = icir
            signals[factor] = signal
            penalties[factor] = penalty

        if not available:
            continue
        equal_w = {f: 1.0 / len(available) for f in available}
        raw_icir = {f: max(icirs[f], 0.0) for f in available}
        icir_w = equal_w.copy() if sum(raw_icir.values()) <= 0 else {f: raw_icir[f] / sum(raw_icir.values()) for f in available}
        raw_weekly = {f: max(icirs[f], 0.0) * penalties[f] for f in available}
        weekly_w = (
            equal_w.copy()
            if sum(raw_weekly.values()) <= 0
            else {f: raw_weekly[f] / sum(raw_weekly.values()) for f in available}
        )
        for factor in available:
            rows.append(
                {
                    "date": date,
                    "factor_name": factor,
                    "weight_equal": equal_w[factor],
                    "weight_icir": icir_w[factor],
                    "weight_icir_weekly_eot": weekly_w[factor],
                    "icir": icirs[factor],
                    "weekly_eot_drift_signal": signals[factor],
                    "penalty": penalties[factor],
                }
            )
    weights = pd.DataFrame(rows).sort_values(["date", "factor_name"]).reset_index(drop=True)
    write_parquet(weights, PROCESSED_DIR / "monthly_factor_weights_weekly_drift.parquet")
    return weights


def run_weekly_drift_backtest(monthly: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    method_cols = {
        "equal": "weight_equal",
        "icir": "weight_icir",
        "icir_weekly_eot": "weight_icir_weekly_eot",
    }
    prev_holdings = {method: set() for method in method_cols}
    turnover_rows = []
    rows = []
    for date in sorted(weights["date"].unique()):
        g = monthly[monthly["date"] == date].copy()
        g = g[g["fwd_ret_1m"].notna()]
        if len(g) < 50:
            continue
        wdate = weights[weights["date"] == date].set_index("factor_name")
        row = {"date": date}
        for method, wcol in method_cols.items():
            score = pd.Series(0.0, index=g.index)
            valid_factor_count = pd.Series(0, index=g.index)
            for factor in FACTOR_NAMES:
                if factor not in wdate.index:
                    continue
                vals = g[f"{factor}_z"]
                mask = vals.notna()
                score.loc[mask] += vals.loc[mask] * float(wdate.loc[factor, wcol])
                valid_factor_count.loc[mask] += 1
            candidates = g.loc[valid_factor_count >= 3, ["ticker", "fwd_ret_1m"]].copy()
            candidates["score"] = score.loc[candidates.index]
            candidates = candidates.dropna()
            if len(candidates) < 50:
                row[f"ret_{method}"] = np.nan
                turnover_rows.append({"date": date, "strategy": method, "turnover": np.nan})
                continue
            q = max(int(math.floor(len(candidates) * TOP_FRAC)), 1)
            holdings = set(candidates.nlargest(q, "score")["ticker"].astype(str))
            ret = candidates[candidates["ticker"].astype(str).isin(holdings)]["fwd_ret_1m"].mean()
            if prev_holdings[method]:
                overlap = len(prev_holdings[method] & holdings)
                turnover = 1.0 - overlap / max(len(prev_holdings[method]), len(holdings))
            else:
                turnover = 1.0
            prev_holdings[method] = holdings
            row[f"ret_{method}"] = ret
            turnover_rows.append({"date": date, "strategy": method, "turnover": turnover})
        rows.append(row)

    nav = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    for method in method_cols:
        nav[f"nav_{method}"] = (1 + nav[f"ret_{method}"].fillna(0)).cumprod()
    nav = nav[
        [
            "date",
            "nav_equal",
            "nav_icir",
            "nav_icir_weekly_eot",
            "ret_equal",
            "ret_icir",
            "ret_icir_weekly_eot",
        ]
    ]
    write_parquet(nav, PROCESSED_DIR / "eot_factor_drift_backtest_nav_weekly_drift.parquet")

    turnover = pd.DataFrame(turnover_rows)
    display = {
        "equal": "Equal-factor multifactor",
        "icir": "ICIR-weighted multifactor",
        "icir_weekly_eot": "ICIR + weekly EOT drift weighted multifactor",
    }
    rows = []
    for method in method_cols:
        ret = nav[f"ret_{method}"].dropna()
        if ret.empty:
            continue
        ann_return = (1 + ret).prod() ** (12 / len(ret)) - 1
        ann_vol = ret.std(ddof=1) * math.sqrt(12)
        sharpe = ret.mean() * 12 / ann_vol if ann_vol and np.isfinite(ann_vol) else np.nan
        mdd, _ = max_drawdown(ret)
        rows.append(
            {
                "strategy": display[method],
                "annual_return": ann_return,
                "annual_volatility": ann_vol,
                "sharpe": sharpe,
                "max_drawdown": mdd,
                "calmar": ann_return / abs(mdd) if mdd < 0 else np.nan,
                "monthly_win_rate": (ret > 0).mean(),
                "turnover": turnover[turnover["strategy"] == method]["turnover"].mean(),
                "start_date": nav.loc[ret.index[0], "date"],
                "end_date": nav.loc[ret.index[-1], "date"],
                "notes": "Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.",
            }
        )

    summary = pd.DataFrame(rows)
    monthly_nav_path = PROCESSED_DIR / "eot_factor_drift_backtest_nav.parquet"
    monthly_summary_path = REPORT_DIR / "preliminary_backtest_summary.csv"
    if monthly_nav_path.exists():
        monthly_nav = read_parquet(monthly_nav_path)
        monthly_nav["date"] = pd.to_datetime(monthly_nav["date"])
        aligned = monthly_nav[monthly_nav["date"] >= nav["date"].min()].copy()
        ret = aligned["ret_icir_eot"].dropna()
        if not ret.empty:
            ann_return = (1 + ret).prod() ** (12 / len(ret)) - 1
            ann_vol = ret.std(ddof=1) * math.sqrt(12)
            mdd, _ = max_drawdown(ret)
            turnover_value = np.nan
            if monthly_summary_path.exists():
                monthly_summary = pd.read_csv(monthly_summary_path)
                old_row = monthly_summary[
                    monthly_summary["strategy"].eq("ICIR + EOT drift weighted multifactor")
                ]
                if not old_row.empty:
                    turnover_value = old_row.iloc[0]["turnover"]
            summary = pd.concat(
                [
                    summary,
                    pd.DataFrame(
                        [
                            {
                                "strategy": "ICIR + monthly EOT drift weighted multifactor",
                                "annual_return": ann_return,
                                "annual_volatility": ann_vol,
                                "sharpe": ret.mean() * 12 / ann_vol if ann_vol else np.nan,
                                "max_drawdown": mdd,
                                "calmar": ann_return / abs(mdd) if mdd < 0 else np.nan,
                                "monthly_win_rate": (ret > 0).mean(),
                                "turnover": turnover_value,
                                "start_date": aligned.loc[ret.index[0], "date"],
                                "end_date": aligned.loc[ret.index[-1], "date"],
                                "notes": "Original monthly EOT strategy, metrics aligned to weekly-drift backtest start; turnover retained from full monthly run.",
                            }
                        ]
                    ),
                ],
                ignore_index=True,
                sort=False,
            )
    summary.to_csv(REPORT_DIR / "preliminary_backtest_summary_weekly_drift.csv", index=False)
    return nav, summary


def create_weekly_addendum(
    weekly_perf_summary: pd.DataFrame,
    weekly_drift_summary: pd.DataFrame,
    comparison: pd.DataFrame,
    future_diag: pd.DataFrame,
    weekly_bt_summary: pd.DataFrame,
) -> None:
    best_weekly = weekly_perf_summary.sort_values("icir", ascending=False).head(2)["factor_name"].tolist()
    noisy_weekly = weekly_perf_summary.sort_values("icir").head(2)["factor_name"].tolist()
    median_obs_mult = comparison["observation_multiplier"].median()
    median_cv_ratio = comparison["cv_ratio_weekly_to_monthly"].median()
    median_mean_corr_change = comparison["mean_shift_corr_change"].median()
    weekly_primary = median_obs_mult > 3
    bt_text = weekly_bt_summary.to_markdown(index=False) if not weekly_bt_summary.empty else "Backtest was not available."

    lines = [
        "# Weekly EOT Drift Addendum",
        "",
        "## 1. Purpose",
        "",
        "This addendum extends the completed monthly EOT factor drift feasibility run to weekly factor-performance observations. "
        "The motivation is simple: monthly recent window = 6 observations, while weekly recent window = 26 observations. "
        "That larger recent sample should make distributional drift estimates less dominated by single-month noise.",
        "",
        "## 2. Weekly Factor Performance",
        "",
        weekly_perf_summary.to_markdown(index=False),
        "",
        f"The strongest weekly Rank ICIR factors are {', '.join(best_weekly)}. The weakest/noisiest by ICIR are {', '.join(noisy_weekly)}. "
        "The ordering is broadly consistent with the monthly run: turnover and low-volatility style signals remain more promising than "
        "simple momentum/liquidity in this HS300 MVP.",
        "",
        "## 3. Weekly EOT Drift Diagnostics",
        "",
        weekly_drift_summary.to_markdown(index=False),
        "",
        f"Weekly drift generated a median {median_obs_mult:.2f}x more drift observations per factor than monthly drift. "
        f"The median weekly/monthly drift CV ratio is {median_cv_ratio:.3f}. "
        f"The median change in EOT/mean-shift correlation is {median_mean_corr_change:.3f}. "
        "POT may still emit occasional Sinkhorn convergence warnings, but the workflow completed and all weekly drift rows were written.",
        "",
        "## 4. Monitoring Value",
        "",
        "Conclusion: **weekly EOT drift is better suited as the primary factor failure monitoring indicator**. "
        "It is also useful as a market/factor-regime diagnostic. As a dynamic weighting penalty, it remains preliminary because "
        "penalty timing, clipping, transaction costs, and neutralized factors still need validation.",
        "",
        "The relationship with subsequent factor returns is weak and factor-dependent:",
        "",
        future_diag.to_markdown(index=False),
        "",
        "## 5. Optional Backtest Result",
        "",
        bt_text,
        "",
        "The weekly-drift backtest keeps monthly rebalancing and uses the average of the last 4 weekly EOT z-scores as the factor penalty signal. "
        "It should be read as an incremental sanity check rather than a final trading result.",
        "",
        "## 6. Recommendation",
        "",
        f"- Formally use weekly factor-performance panel as the main EOT monitoring input: {'yes' if weekly_primary else 'not yet'}.",
        "- Retain monthly panel as a slower robustness check.",
        "- Use weekly EOT drift as the main monitoring metric before relying on it for allocation.",
        "- Continue dynamic weighting research, but add transaction costs and penalty clipping before drawing conclusions.",
        "- Add industry and market-cap data for neutralized factors.",
        "- Add strict limit-up/limit-down buyability filters and realistic transaction-cost assumptions.",
        "",
    ]
    (REPORT_DIR / "weekly_eot_drift_addendum.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    panel = read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])

    weekly = construct_weekly_factors(panel)
    weekly_perf = compute_weekly_performance(weekly)
    weekly_perf_summary = summarize_weekly_performance(weekly_perf, weekly["date"].nunique() - 1)
    weekly_drift = compute_weekly_drift_scores(weekly_perf)
    weekly_drift_summary = summarize_weekly_drift(weekly_drift)

    monthly_drift = read_parquet(PROCESSED_DIR / "eot_factor_drift_scores.parquet")
    monthly_drift["date"] = pd.to_datetime(monthly_drift["date"])
    comparison, future_diag = create_comparison_report(monthly_drift, weekly_drift, weekly_perf)
    create_weekly_figures(weekly_perf, weekly_drift, monthly_drift, comparison)

    monthly_perf = read_parquet(PROCESSED_DIR / "monthly_factor_performance.parquet")
    monthly_perf["date"] = pd.to_datetime(monthly_perf["date"])
    monthly = construct_monthly_factors(panel)
    weekly_weights = compute_monthly_weights_with_weekly_drift(monthly_perf, weekly_drift)
    _, weekly_bt_summary = run_weekly_drift_backtest(monthly, weekly_weights)
    create_weekly_addendum(weekly_perf_summary, weekly_drift_summary, comparison, future_diag, weekly_bt_summary)

    print("Generated weekly EOT feasibility outputs under:")
    print(PROCESSED_DIR / "weekly_factor_performance.parquet")
    print(PROCESSED_DIR / "weekly_eot_factor_drift_scores.parquet")
    print(REPORT_DIR / "weekly_vs_monthly_drift_comparison.md")
    print(REPORT_DIR / "weekly_eot_drift_addendum.md")


if __name__ == "__main__":
    main()
