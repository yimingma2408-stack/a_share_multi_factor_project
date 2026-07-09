from __future__ import annotations

import math

import pandas as pd


def quantile_group_returns(
    df: pd.DataFrame,
    factor_col: str,
    forward_return_col: str,
    date_col: str = "date",
    groups: int = 5,
    min_obs: int = 30,
) -> pd.DataFrame:
    rows = []
    for date, g in df.groupby(date_col, sort=True):
        valid = g[[factor_col, forward_return_col]].dropna().copy()
        if len(valid) < min_obs:
            continue
        valid["group"] = pd.qcut(valid[factor_col].rank(method="first"), groups, labels=False) + 1
        grouped = valid.groupby("group")[forward_return_col].mean()
        row = {"date": date, "factor_name": factor_col, "n_obs": len(valid)}
        for group, ret in grouped.items():
            row[f"group_{int(group)}_return"] = ret
        row["long_short_return"] = grouped.get(groups, math.nan) - grouped.get(1, math.nan)
        rows.append(row)
    return pd.DataFrame(rows)

