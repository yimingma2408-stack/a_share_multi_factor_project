from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loader import require_columns


QUALITY_GROWTH_INPUT_COLUMNS = [
    "ticker",
    "date",
    "report_date",
    "announcement_date",
    "book_equity",
    "total_assets",
    "net_profit",
    "revenue",
    "gross_profit",
    "operating_cash_flow",
    "market_cap",
]


def _positive_denominator(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").astype(float)
    return x.where(x > 0)


def build_quality_growth_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Build ROE, gross profitability, cash-flow quality, growth, and size factors."""
    require_columns(df, QUALITY_GROWTH_INPUT_COLUMNS, "fundamental panel")
    out = df.copy()
    out["ticker"] = out["ticker"].astype(str).str.zfill(6)
    out["date"] = pd.to_datetime(out["date"])
    out["report_date"] = pd.to_datetime(out["report_date"])
    out["announcement_date"] = pd.to_datetime(out["announcement_date"])

    book_equity = _positive_denominator(out["book_equity"])
    total_assets = _positive_denominator(out["total_assets"])
    market_cap = _positive_denominator(out["market_cap"])
    out["size"] = np.log(market_cap)
    out["roe"] = pd.to_numeric(out["net_profit"], errors="coerce") / book_equity
    out["gross_profitability"] = pd.to_numeric(out["gross_profit"], errors="coerce") / total_assets
    out["ocf_to_assets"] = pd.to_numeric(out["operating_cash_flow"], errors="coerce") / total_assets

    statements = (
        out[
            [
                "ticker",
                "report_date",
                "announcement_date",
                "revenue",
                "net_profit",
            ]
        ]
        .dropna(subset=["ticker", "report_date", "announcement_date"])
        .drop_duplicates(["ticker", "report_date", "announcement_date"], keep="last")
        .sort_values(["ticker", "report_date", "announcement_date"])
        .copy()
    )
    for col in ["revenue", "net_profit"]:
        statements[col] = pd.to_numeric(statements[col], errors="coerce")
        previous = statements.groupby("ticker")[col].shift(4)
        growth = statements[col] / previous.where(previous.abs() > 1e-12) - 1.0
        statements[f"{col}_growth"] = growth.replace([np.inf, -np.inf], np.nan)

    growth = statements[["ticker", "report_date", "announcement_date", "revenue_growth", "net_profit_growth"]]
    out = out.merge(growth, on=["ticker", "report_date", "announcement_date"], how="left")
    out = out.rename(columns={"net_profit_growth": "earnings_growth"})
    return out


def build_market_return(
    df: pd.DataFrame,
    ret_col: str = "return_1d",
    date_col: str = "date",
) -> pd.DataFrame:
    require_columns(df, [date_col, ret_col], "daily return panel")
    out = df[[date_col, ret_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out[ret_col] = pd.to_numeric(out[ret_col], errors="coerce")
    return out.groupby(date_col)[ret_col].mean().rename("market_return").reset_index()


def build_rolling_risk_factors(
    df: pd.DataFrame,
    ret_col: str = "return_1d",
    ticker_col: str = "ticker",
    date_col: str = "date",
    window: int = 252,
    min_periods: int = 126,
) -> pd.DataFrame:
    """Build rolling beta, idiosyncratic volatility, and downside beta."""
    require_columns(df, [ticker_col, date_col, ret_col], "daily return panel")
    daily = df[[ticker_col, date_col, ret_col]].copy()
    daily[ticker_col] = daily[ticker_col].astype(str).str.zfill(6)
    daily[date_col] = pd.to_datetime(daily[date_col])
    daily[ret_col] = pd.to_numeric(daily[ret_col], errors="coerce")
    market = build_market_return(daily, ret_col=ret_col, date_col=date_col)
    daily = daily.merge(market, on=date_col, how="left").sort_values([ticker_col, date_col])

    frames = []
    for ticker, group in daily.groupby(ticker_col, sort=False):
        g = group.copy()
        y = g[ret_col]
        x = g["market_return"]
        rolling_cov = y.rolling(window, min_periods=min_periods).cov(x)
        rolling_var = x.rolling(window, min_periods=min_periods).var()
        beta = rolling_cov / rolling_var.where(rolling_var > 1e-12)
        residual = y - beta * x

        downside_mask = x < 0
        x_down = x.where(downside_mask)
        y_down = y.where(downside_mask)
        n = downside_mask.astype(float).rolling(window, min_periods=min_periods).sum()
        sum_x = x_down.fillna(0.0).rolling(window, min_periods=min_periods).sum()
        sum_y = y_down.fillna(0.0).rolling(window, min_periods=min_periods).sum()
        sum_xy = (x_down * y_down).fillna(0.0).rolling(window, min_periods=min_periods).sum()
        sum_x2 = (x_down * x_down).fillna(0.0).rolling(window, min_periods=min_periods).sum()
        cov_num = sum_xy - (sum_x * sum_y / n.where(n > 0))
        var_num = sum_x2 - (sum_x * sum_x / n.where(n > 0))
        downside_beta = cov_num / var_num.where(var_num > 1e-12)

        g["rolling_beta"] = beta
        g["idiosyncratic_volatility"] = residual.rolling(window, min_periods=min_periods).std() * np.sqrt(252.0)
        g["downside_beta"] = downside_beta
        frames.append(g[[date_col, ticker_col, "rolling_beta", "idiosyncratic_volatility", "downside_beta"]])

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
