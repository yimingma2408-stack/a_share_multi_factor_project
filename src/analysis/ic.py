from __future__ import annotations

import pandas as pd


def compute_rank_ic(
    df: pd.DataFrame,
    factor_cols: list[str],
    forward_return_col: str,
    date_col: str = "date",
    min_obs: int = 30,
) -> pd.DataFrame:
    rows = []
    for date, g in df.groupby(date_col, sort=True):
        for factor in factor_cols:
            valid = g[[factor, forward_return_col]].dropna()
            if len(valid) < min_obs:
                continue
            rows.append(
                {
                    "date": date,
                    "factor_name": factor,
                    "ic": valid[factor].corr(valid[forward_return_col], method="pearson"),
                    "rank_ic": valid[factor].corr(valid[forward_return_col], method="spearman"),
                    "n_obs": len(valid),
                }
            )
    return pd.DataFrame(rows)


def summarize_ic(ic: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor, g in ic.groupby("factor_name"):
        std = g["rank_ic"].std(ddof=1)
        rows.append(
            {
                "factor_name": factor,
                "mean_rank_ic": g["rank_ic"].mean(),
                "std_rank_ic": std,
                "rank_icir": g["rank_ic"].mean() / std if std and pd.notna(std) else float("nan"),
                "rank_ic_win_rate": (g["rank_ic"] > 0).mean(),
                "observations": len(g),
            }
        )
    return pd.DataFrame(rows)

