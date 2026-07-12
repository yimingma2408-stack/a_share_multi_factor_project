from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_past_stat(series: pd.Series, window: int, min_periods: int, stat: str) -> pd.Series:
    """Rolling statistic using observations strictly before the current row."""
    shifted = pd.to_numeric(series, errors="coerce").shift(1)
    roll = shifted.rolling(window, min_periods=min_periods)
    if stat == "mean":
        return roll.mean()
    if stat == "std":
        return roll.std(ddof=1)
    raise ValueError(f"Unsupported stat: {stat}")


def normalized_nonnegative_weights(values: pd.Series) -> pd.Series:
    raw = pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0.0)
    if raw.sum() <= 0:
        return pd.Series(1.0 / len(raw), index=raw.index) if len(raw) else raw
    return raw / raw.sum()


def apply_family_weight_cap(
    weights: pd.Series,
    families: pd.Series,
    cap: float = 0.65,
    max_iter: int = 20,
) -> pd.Series:
    """Normalize weights while iteratively enforcing a per-family cap."""
    w = normalized_nonnegative_weights(weights)
    fam = families.reindex(w.index)
    if fam.nunique() <= 1:
        return w
    for _ in range(max_iter):
        totals = w.groupby(fam).sum()
        over = totals[totals > cap + 1e-12]
        if over.empty:
            break
        locked = pd.Series(False, index=w.index)
        for family, total in over.items():
            mask = fam == family
            w.loc[mask] *= cap / total
            locked |= mask
        residual = 1.0 - w.sum()
        free = ~locked
        if residual <= 1e-12 or w.loc[free].sum() <= 0:
            break
        w.loc[free] += residual * w.loc[free] / w.loc[free].sum()
    return w / w.sum()


def drift_penalty(drift: pd.Series, eta: float = 1.0, lower: float = 0.5) -> pd.Series:
    d = pd.to_numeric(drift, errors="coerce").fillna(0.0).clip(lower=0.0)
    return (1.0 / (1.0 + eta * d)).clip(lower=lower, upper=1.0)


def transaction_cost(gross_return: pd.Series, turnover: pd.Series, cost_bps: float) -> pd.Series:
    return pd.to_numeric(gross_return, errors="coerce") - pd.to_numeric(turnover, errors="coerce").fillna(0) * cost_bps / 10000.0


def map_weekly_signal_to_rebalance(
    weekly: pd.DataFrame,
    rebalance_dates: pd.Series | list[pd.Timestamp],
    date_col: str = "date",
) -> pd.DataFrame:
    """Backward as-of map; mapped signals can never come from the future."""
    left = pd.DataFrame({"rebalance_date": pd.to_datetime(pd.Series(rebalance_dates))}).sort_values("rebalance_date")
    right = weekly.copy().sort_values(date_col)
    right[date_col] = pd.to_datetime(right[date_col])
    out = pd.merge_asof(left, right, left_on="rebalance_date", right_on=date_col, direction="backward")
    if (out[date_col] > out["rebalance_date"]).fillna(False).any():
        raise AssertionError("Future weekly signal mapped to a rebalance date")
    return out
