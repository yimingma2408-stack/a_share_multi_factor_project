from __future__ import annotations

import pandas as pd


def factor_correlation(df: pd.DataFrame, factor_cols: list[str], method: str = "spearman") -> pd.DataFrame:
    return df[factor_cols].corr(method=method)


def factor_correlation_by_year(
    df: pd.DataFrame,
    factor_cols: list[str],
    date_col: str = "date",
    method: str = "spearman",
) -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    rows = []
    for year, g in out.groupby(out[date_col].dt.year):
        corr = g[factor_cols].corr(method=method)
        for left in factor_cols:
            for right in factor_cols:
                rows.append({"year": year, "factor_left": left, "factor_right": right, "correlation": corr.loc[left, right]})
    return pd.DataFrame(rows)

