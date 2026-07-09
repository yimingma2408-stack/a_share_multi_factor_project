from __future__ import annotations

import math

import numpy as np
import pandas as pd


def market_model_regression(
    returns: pd.DataFrame,
    portfolio_return_col: str = "portfolio_return",
    benchmark_return_col: str = "benchmark_return",
) -> dict[str, float]:
    required = {portfolio_return_col, benchmark_return_col}
    if not required.issubset(returns.columns):
        raise ValueError(f"returns must contain {sorted(required)}")

    valid = returns[[portfolio_return_col, benchmark_return_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < 12:
        raise ValueError("market regression needs at least 12 observations")

    x = np.column_stack([np.ones(len(valid)), valid[benchmark_return_col].to_numpy(dtype=float)])
    y = valid[portfolio_return_col].to_numpy(dtype=float)
    alpha, beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ np.array([alpha, beta])
    dof = max(len(valid) - 2, 1)
    sigma2 = float(np.dot(residual, residual) / dof)
    xtx_inv = np.linalg.pinv(x.T @ x)
    se = np.sqrt(np.diag(sigma2 * xtx_inv))
    return {
        "alpha": float(alpha),
        "beta": float(beta),
        "alpha_t_stat": float(alpha / se[0]) if se[0] > 0 else math.nan,
        "beta_t_stat": float(beta / se[1]) if se[1] > 0 else math.nan,
        "r_squared": float(1.0 - residual.var() / y.var()) if y.var() > 0 else math.nan,
        "observations": float(len(valid)),
    }


def portfolio_exposure(
    holdings: pd.DataFrame,
    exposures: pd.DataFrame,
    exposure_cols: list[str],
    date_col: str = "date",
    ticker_col: str = "ticker",
    weight_col: str = "weight",
) -> pd.DataFrame:
    required_holdings = {date_col, ticker_col, weight_col}
    if not required_holdings.issubset(holdings.columns):
        raise ValueError(f"holdings must contain {sorted(required_holdings)}")
    required_exposures = {date_col, ticker_col, *exposure_cols}
    if not required_exposures.issubset(exposures.columns):
        raise ValueError(f"exposures must contain {sorted(required_exposures)}")

    merged = holdings.merge(exposures[[date_col, ticker_col] + exposure_cols], on=[date_col, ticker_col], how="left")
    rows = []
    for date, g in merged.groupby(date_col, sort=True):
        row = {"date": date}
        weights = pd.to_numeric(g[weight_col], errors="coerce").fillna(0.0)
        for col in exposure_cols:
            values = pd.to_numeric(g[col], errors="coerce")
            row[col] = float((weights * values).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def industry_weight_exposure(
    holdings: pd.DataFrame,
    industry: pd.DataFrame,
    date_col: str = "date",
    ticker_col: str = "ticker",
    weight_col: str = "weight",
    industry_col: str = "industry",
) -> pd.DataFrame:
    required_industry = {date_col, ticker_col, industry_col}
    if not required_industry.issubset(industry.columns):
        raise ValueError(f"industry data must contain {sorted(required_industry)}")
    merged = holdings.merge(industry[[date_col, ticker_col, industry_col]], on=[date_col, ticker_col], how="left")
    out = (
        merged.groupby([date_col, industry_col], dropna=False)[weight_col]
        .sum()
        .rename("portfolio_weight")
        .reset_index()
    )
    return out
