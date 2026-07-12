"""Reusable workflow primitives for formal EOT-map lifecycle experiments."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_quality_features(
    performance: pd.DataFrame,
    base_window: int = 156,
    recent_window: int = 26,
) -> pd.DataFrame:
    """Compute strictly past-only historical/recent ICIR features by factor."""
    parts = []
    for _, group in performance.sort_values("date").groupby("factor_name"):
        out = group.copy()
        prior_ic = pd.to_numeric(out["rank_ic"], errors="coerce").shift(1)
        historical_min = min(base_window, max(52, recent_window))
        recent_min = min(recent_window, max(13, recent_window // 2))
        historical_mean = prior_ic.rolling(base_window, min_periods=historical_min).mean()
        historical_std = prior_ic.rolling(base_window, min_periods=historical_min).std(ddof=1)
        recent_mean = prior_ic.rolling(recent_window, min_periods=recent_min).mean()
        recent_std = prior_ic.rolling(recent_window, min_periods=recent_min).std(ddof=1)
        out["historical_icir"] = historical_mean / historical_std.replace(0, np.nan)
        out["recent_icir"] = recent_mean / recent_std.replace(0, np.nan)
        out["quality_trend"] = out["recent_icir"] - out["historical_icir"]
        parts.append(out)
    return pd.concat(parts, ignore_index=True) if parts else performance.copy()


def coordinate_mean_permutation_pvalues(
    base: np.ndarray,
    recent: np.ndarray,
    rng: np.random.Generator,
    repetitions: int = 199,
) -> np.ndarray:
    """Post-hoc two-sample mean permutation p-values for coordinate follow-up."""
    observed = np.abs(recent.mean(axis=0) - base.mean(axis=0))
    pooled, n_base = np.vstack([base, recent]), len(base)
    exceedances = np.zeros(base.shape[1])
    for _ in range(repetitions):
        index = rng.permutation(len(pooled))
        statistic = np.abs(pooled[index[n_base:]].mean(axis=0) - pooled[index[:n_base]].mean(axis=0))
        exceedances += statistic >= observed
    return (exceedances + 1) / (repetitions + 1)


def month_end_signals(signal: pd.DataFrame, date_col: str = "date", factor_col: str = "factor_name") -> pd.DataFrame:
    """Map weekly monitoring to the final available signal in every calendar month."""
    out = signal.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out["_rebalance_month"] = out[date_col].dt.to_period("M")
    out = (
        out.sort_values(date_col)
        .groupby([factor_col, "_rebalance_month"], as_index=False)
        .tail(1)
        .drop(columns="_rebalance_month")
    )
    return out


def attach_latest_monthly_weights(
    dashboard: pd.DataFrame,
    monthly_weights: pd.DataFrame,
    date_col: str = "date",
    factor_col: str = "factor_name",
    weight_col: str = "final_weight",
) -> pd.DataFrame:
    """Carry the latest available monthly weight to each later weekly dashboard row."""
    left = dashboard.copy()
    right = monthly_weights[[date_col, factor_col, weight_col]].copy()
    left[date_col] = pd.to_datetime(left[date_col])
    right[date_col] = pd.to_datetime(right[date_col])
    left[factor_col] = left[factor_col].astype(str)
    right[factor_col] = right[factor_col].astype(str)
    out = pd.merge_asof(
        left.sort_values([date_col, factor_col]),
        right.sort_values([date_col, factor_col]),
        on=date_col,
        by=factor_col,
        direction="backward",
    )
    return out
