from __future__ import annotations

import numpy as np
import pandas as pd


def _mad_winsorize(values: pd.Series, n: float = 3.0) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    median = x.median()
    mad = (x - median).abs().median()
    if not np.isfinite(mad) or mad <= 1e-12:
        return x
    scale = 1.4826 * mad
    return x.clip(median - n * scale, median + n * scale)


def _zscore(values: pd.Series) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce")
    std = x.std(ddof=0)
    if not np.isfinite(std) or std <= 1e-12:
        return pd.Series(np.nan, index=values.index)
    return (x - x.mean()) / std


def preprocess_factor_cross_section(
    df: pd.DataFrame,
    factor_col: str,
    date_col: str = "date",
    industry_col: str = "industry",
    size_col: str = "float_market_cap",
    winsor_method: str = "mad",
    winsor_n: float = 3.0,
    neutralize: bool = True,
) -> pd.DataFrame:
    """PIT-safe cross-sectional winsorization, neutralization and z-scoring.

    The function does not shift dates or calculate forward returns.  It only uses
    observations in each supplied cross-section.  Diagnostics are repeated on
    each row so callers can aggregate them without hidden global state.
    """
    if winsor_method != "mad":
        raise ValueError("Only winsor_method='mad' is supported")
    required = {date_col, factor_col}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns: {sorted(missing)}")

    out = df.copy()
    output_col = f"{factor_col}_processed"
    out[output_col] = np.nan
    diagnostics: list[pd.DataFrame] = []
    for _, index in out.groupby(date_col, sort=False).groups.items():
        group = out.loc[index]
        raw = pd.to_numeric(group[factor_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        clipped = _mad_winsorize(raw, winsor_n)
        first_z = _zscore(clipped)
        final = first_z.copy()

        design = pd.DataFrame({"intercept": 1.0}, index=group.index)
        if neutralize and size_col in group.columns:
            size = pd.to_numeric(group[size_col], errors="coerce")
            design["log_size"] = np.log(size.where(size > 0))
        if neutralize and industry_col in group.columns and group[industry_col].notna().any():
            dummies = pd.get_dummies(group[industry_col].astype("category"), drop_first=True, dtype=float)
            design = design.join(dummies)

        if neutralize and design.shape[1] > 1:
            valid = first_z.notna() & design.replace([np.inf, -np.inf], np.nan).notna().all(axis=1)
            if valid.sum() > design.shape[1] + 2:
                x = design.loc[valid].to_numpy(dtype=float)
                beta = np.linalg.lstsq(x, first_z.loc[valid].to_numpy(dtype=float), rcond=None)[0]
                final = pd.Series(np.nan, index=group.index)
                final.loc[valid] = first_z.loc[valid] - x @ beta
        final = _zscore(final)
        out.loc[index, output_col] = final

        n = max(len(group), 1)
        diag = pd.DataFrame(
            {
                "raw_coverage": raw.notna().sum() / n,
                "post_filter_coverage": clipped.notna().sum() / n,
                "post_neutralization_coverage": final.notna().sum() / n,
                "cross_section_std": final.std(ddof=0),
            },
            index=index,
        )
        diagnostics.append(diag)
    if diagnostics:
        diag = pd.concat(diagnostics).sort_index()
        for col in diag:
            out.loc[diag.index, col] = diag[col]
    return out
