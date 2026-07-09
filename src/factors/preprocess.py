from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize_series(s: pd.Series, lower_q: float = 0.01, upper_q: float = 0.99) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").astype(float)
    valid = x.dropna()
    if valid.empty:
        return x
    lo, hi = valid.quantile([lower_q, upper_q])
    return x.clip(lo, hi)


def zscore_series(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").astype(float)
    std = x.std(ddof=0)
    if not np.isfinite(std) or std <= 1e-12:
        return pd.Series(np.nan, index=s.index)
    return (x - x.mean()) / std


def preprocess_by_date(
    df: pd.DataFrame,
    factor_cols: list[str],
    date_col: str = "date",
    lower_q: float = 0.01,
    upper_q: float = 0.99,
) -> pd.DataFrame:
    out = df.copy()
    for col in factor_cols:
        out[f"{col}_z"] = out.groupby(date_col)[col].transform(
            lambda s: zscore_series(winsorize_series(s, lower_q, upper_q))
        )
    return out


def neutralize_cross_section(
    frame: pd.DataFrame,
    factor_col: str,
    size_col: str | None = None,
    industry_col: str | None = None,
) -> pd.Series:
    y = pd.to_numeric(frame[factor_col], errors="coerce").astype(float)
    design = pd.DataFrame({"intercept": 1.0}, index=frame.index)

    if size_col and size_col in frame.columns:
        size = pd.to_numeric(frame[size_col], errors="coerce").astype(float)
        design["log_size"] = np.log(size.where(size > 0))
    if industry_col and industry_col in frame.columns:
        dummies = pd.get_dummies(frame[industry_col].astype("category"), prefix="industry", drop_first=True)
        design = design.join(dummies.astype(float))

    valid = y.notna() & design.replace([np.inf, -np.inf], np.nan).notna().all(axis=1)
    resid = pd.Series(np.nan, index=frame.index)
    if valid.sum() <= design.loc[valid].shape[1] + 2:
        return resid

    x = design.loc[valid].to_numpy(dtype=float)
    beta = np.linalg.lstsq(x, y.loc[valid].to_numpy(dtype=float), rcond=None)[0]
    resid.loc[valid] = y.loc[valid] - x @ beta
    return resid


def neutralize_by_date(
    df: pd.DataFrame,
    factor_cols: list[str],
    date_col: str = "date",
    size_col: str | None = None,
    industry_col: str | None = None,
) -> pd.DataFrame:
    out = df.copy()
    for factor in factor_cols:
        out[f"{factor}_neutral"] = out.groupby(date_col, group_keys=False).apply(
            lambda g: neutralize_cross_section(g, factor, size_col=size_col, industry_col=industry_col),
            include_groups=False,
        )
    return out

