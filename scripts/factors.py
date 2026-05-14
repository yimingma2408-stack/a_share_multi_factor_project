import pandas as pd


def add_daily_return(
    df: pd.DataFrame,
    price_col: str = "close",
) -> pd.DataFrame:
    """
    为每只股票计算日收益率（日频收益率因子）

    日收益率计算公式：ret_1d = (price_t - price_{t-1}) / price_{t-1}

    Args:
        df: 股票面板数据，必须包含列：
            - ticker: 股票代码
            - date: 交易日期
            - price_col: 价格列（默认"close"，即收盘价）
        price_col: 用于计算收益率的价格列名称，默认为"close"

    Returns:
        新增"ret_1d"列的DataFrame，包含每日收益率

    Notes:
        - 函数会先按ticker和date排序，确保时序正确
        - 每只股票的第一个交易日ret_1d为NaN（无前置数据）
        - 返回的是数据副本，不修改原DataFrame
    """
    # 按股票代码和日期排序，确保时间顺序正确（收益率计算的前提）
    df = df.sort_values(["ticker", "date"]).copy()

    # 按股票分组，计算每组价格的日变化百分比（即日收益率）
    df["ret_1d"] = df.groupby("ticker")[price_col].pct_change()

    return df



def add_forward_return(
    df: pd.DataFrame,
    price_col: str = "close",
    horizon: int = 20,
) -> pd.DataFrame:
    """
    Add forward return over a given horizon.

    This is the future return to be predicted by factors.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    future_price = df.groupby("ticker")[price_col].shift(-horizon)
    df[f"fwd_ret_{horizon}d"] = future_price / df[price_col] - 1

    return df


def add_reversal_factor(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
) -> pd.DataFrame:
    """
    Short-term reversal factor.

    Higher value means stronger past underperformance.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    past_ret = df.groupby("ticker")[price_col].pct_change(window)
    df[f"rev_{window}d"] = -past_ret

    return df


def add_momentum_factor(
    df: pd.DataFrame,
    price_col: str = "close",
    lookback: int = 120,
    skip: int = 20,
) -> pd.DataFrame:
    """
    Medium-term momentum factor.

    Use return from t-lookback to t-skip.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    price_lag_skip = df.groupby("ticker")[price_col].shift(skip)
    price_lag_lookback = df.groupby("ticker")[price_col].shift(lookback)

    df[f"mom_{lookback}_{skip}d"] = price_lag_skip / price_lag_lookback - 1

    return df


def add_volatility_factor(
    df: pd.DataFrame,
    ret_col: str = "ret_1d",
    window: int = 60,
) -> pd.DataFrame:
    """
    Low-volatility factor.

    Higher value means lower past volatility.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    vol = (
        df.groupby("ticker")[ret_col]
        .rolling(window)
        .std()
        .reset_index(level=0, drop=True)
    )

    df[f"vol_{window}d"] = vol
    df[f"lowvol_{window}d"] = -vol

    return df


def add_liquidity_factor(
    df: pd.DataFrame,
    amount_col: str = "amount",
    window: int = 20,
) -> pd.DataFrame:
    """
    Liquidity factor based on rolling average amount.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    avg_amount = (
        df.groupby("ticker")[amount_col]
        .rolling(window)
        .mean()
        .reset_index(level=0, drop=True)
    )

    df[f"liq_{window}d"] = avg_amount

    return df


def add_turnover_factor(
    df: pd.DataFrame,
    turnover_col: str = "turnover",
    window: int = 20,
) -> pd.DataFrame:
    """
    Rolling average turnover factor.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    avg_turnover = (
        df.groupby("ticker")[turnover_col]
        .rolling(window)
        .mean()
        .reset_index(level=0, drop=True)
    )

    df[f"turnover_{window}d"] = avg_turnover

    return df


def add_trend_factor(
    df: pd.DataFrame,
    price_col: str = "close",
    short_window: int = 20,
    long_window: int = 120,
) -> pd.DataFrame:
    """
    Moving-average trend factor.
    """
    df = df.sort_values(["ticker", "date"]).copy()

    ma_short = (
        df.groupby("ticker")[price_col]
        .rolling(short_window)
        .mean()
        .reset_index(level=0, drop=True)
    )

    ma_long = (
        df.groupby("ticker")[price_col]
        .rolling(long_window)
        .mean()
        .reset_index(level=0, drop=True)
    )

    df[f"trend_{short_window}_{long_window}d"] = ma_short / ma_long - 1

    return df