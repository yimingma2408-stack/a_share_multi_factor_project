from __future__ import annotations

import pandas as pd

from src.analysis.ic import compute_rank_ic
from src.data.loader import require_columns


def add_forward_returns(
    df: pd.DataFrame,
    horizons: tuple[int, ...] = (1, 5, 10, 20, 60),
    price_col: str = "close",
    ticker_col: str = "ticker",
    date_col: str = "date",
) -> pd.DataFrame:
    require_columns(df, [ticker_col, date_col, price_col], "price panel")
    out = df.sort_values([ticker_col, date_col]).copy()
    grouped = out.groupby(ticker_col)[price_col]
    for horizon in horizons:
        out[f"fwd_ret_{horizon}d"] = grouped.shift(-horizon) / out[price_col] - 1.0
    return out


def compute_ic_decay(
    df: pd.DataFrame,
    factor_cols: list[str],
    horizons: tuple[int, ...] = (1, 5, 10, 20, 60),
    date_col: str = "date",
    min_obs: int = 30,
) -> pd.DataFrame:
    rows = []
    for horizon in horizons:
        ret_col = f"fwd_ret_{horizon}d"
        if ret_col not in df.columns:
            continue
        ic = compute_rank_ic(df, factor_cols, ret_col, date_col=date_col, min_obs=min_obs)
        if ic.empty:
            continue
        summary = (
            ic.groupby("factor_name")["rank_ic"]
            .agg(["mean", "std", "count"])
            .reset_index()
            .rename(columns={"mean": "mean_rank_ic", "std": "std_rank_ic", "count": "observations"})
        )
        summary["horizon_days"] = horizon
        rows.append(summary)
    if not rows:
        return pd.DataFrame(columns=["factor_name", "mean_rank_ic", "std_rank_ic", "observations", "horizon_days"])
    out = pd.concat(rows, ignore_index=True)
    out["rank_icir"] = out["mean_rank_ic"] / out["std_rank_ic"]
    return out[["factor_name", "horizon_days", "mean_rank_ic", "std_rank_ic", "rank_icir", "observations"]]
