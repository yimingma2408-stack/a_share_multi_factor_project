from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loader import require_columns


def add_return_columns(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    require_columns(df, ["ticker", "date", price_col], "daily price data")
    out = df.sort_values(["ticker", "date"]).copy()
    out["ret_1d"] = out.groupby("ticker")[price_col].pct_change()
    return out


def add_momentum(
    df: pd.DataFrame,
    price_col: str = "close",
    windows: tuple[int, ...] = (20, 60, 120, 250),
    skip: int = 20,
) -> pd.DataFrame:
    require_columns(df, ["ticker", "date", price_col], "daily price data")
    out = df.sort_values(["ticker", "date"]).copy()
    grouped = out.groupby("ticker")[price_col]
    for window in windows:
        if window <= skip:
            out[f"mom_{window}d"] = grouped.pct_change(window)
        else:
            out[f"mom_{window}_{skip}d"] = grouped.shift(skip) / grouped.shift(window) - 1.0
    return out


def add_reversal(df: pd.DataFrame, price_col: str = "close", window: int = 20) -> pd.DataFrame:
    require_columns(df, ["ticker", "date", price_col], "daily price data")
    out = df.sort_values(["ticker", "date"]).copy()
    out[f"reversal_{window}d"] = -out.groupby("ticker")[price_col].pct_change(window)
    return out


def add_low_volatility(
    df: pd.DataFrame,
    ret_col: str = "ret_1d",
    windows: tuple[int, ...] = (20, 60, 120, 250),
    annualize: bool = True,
) -> pd.DataFrame:
    require_columns(df, ["ticker", "date", ret_col], "return data")
    out = df.sort_values(["ticker", "date"]).copy()
    grouped = out.groupby("ticker")[ret_col]
    scale = np.sqrt(252.0) if annualize else 1.0
    for window in windows:
        vol = grouped.rolling(window, min_periods=max(5, window // 2)).std().reset_index(level=0, drop=True)
        out[f"vol_{window}d"] = vol * scale
        out[f"lowvol_{window}d"] = -out[f"vol_{window}d"]
    return out


def add_turnover_factors(
    df: pd.DataFrame,
    turnover_col: str = "turnover",
    windows: tuple[int, ...] = (20, 60),
) -> pd.DataFrame:
    require_columns(df, ["ticker", "date", turnover_col], "turnover data")
    out = df.sort_values(["ticker", "date"]).copy()
    grouped = out.groupby("ticker")[turnover_col]
    for window in windows:
        avg = grouped.rolling(window, min_periods=max(5, window // 2)).mean().reset_index(level=0, drop=True)
        out[f"turnover_{window}d"] = avg
        out[f"lowturn_{window}d"] = -np.log1p(avg.clip(lower=0))
    return out


def add_liquidity_factor(df: pd.DataFrame, amount_col: str = "amount", window: int = 20) -> pd.DataFrame:
    require_columns(df, ["ticker", "date", amount_col], "amount data")
    out = df.sort_values(["ticker", "date"]).copy()
    avg = (
        out.groupby("ticker")[amount_col]
        .rolling(window, min_periods=max(5, window // 2))
        .mean()
        .reset_index(level=0, drop=True)
    )
    out[f"liquidity_{window}d"] = np.log1p(avg.clip(lower=0))
    return out


def build_price_volume_factor_panel(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    out = add_return_columns(df, price_col=price_col)
    out = add_momentum(out, price_col=price_col)
    out = add_reversal(out, price_col=price_col)
    out = add_low_volatility(out)
    if "turnover" in out.columns:
        out = add_turnover_factors(out)
    if "amount" in out.columns:
        out = add_liquidity_factor(out)
    return out

