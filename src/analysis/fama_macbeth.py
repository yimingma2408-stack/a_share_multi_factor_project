from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _newey_west_se(x: pd.Series, lags: int = 3) -> float:
    values = pd.to_numeric(x, errors="coerce").dropna().to_numpy(dtype=float)
    n = len(values)
    if n < 3:
        return float("nan")
    centered = values - values.mean()
    gamma0 = float(np.dot(centered, centered) / n)
    var = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        cov = float(np.dot(centered[lag:], centered[:-lag]) / n)
        var += 2.0 * (1.0 - lag / (lags + 1.0)) * cov
    return math.sqrt(max(var, 0.0) / n)


def run_fama_macbeth(
    df: pd.DataFrame,
    factor_cols: list[str],
    forward_return_col: str,
    date_col: str = "date",
    min_obs: int = 30,
    nw_lags: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    betas = []
    cols = ["intercept"] + factor_cols
    for date, g in df.groupby(date_col, sort=True):
        valid = g[factor_cols + [forward_return_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) < max(min_obs, len(cols) + 3):
            continue
        x = np.column_stack([np.ones(len(valid)), valid[factor_cols].to_numpy(dtype=float)])
        y = valid[forward_return_col].to_numpy(dtype=float)
        coef = np.linalg.lstsq(x, y, rcond=None)[0]
        betas.append({"date": date, **dict(zip(cols, coef))})

    beta_ts = pd.DataFrame(betas)
    summary_rows = []
    for col in cols:
        if col not in beta_ts:
            continue
        mean = beta_ts[col].mean()
        se = _newey_west_se(beta_ts[col], lags=nw_lags)
        summary_rows.append(
            {
                "term": col,
                "mean_coefficient": mean,
                "newey_west_se": se,
                "t_stat": mean / se if se and np.isfinite(se) else float("nan"),
                "observations": beta_ts[col].notna().sum(),
            }
        )
    return beta_ts, pd.DataFrame(summary_rows)

