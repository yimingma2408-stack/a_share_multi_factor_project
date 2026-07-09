from __future__ import annotations

import math

import pandas as pd


def max_drawdown(returns: pd.Series) -> float:
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return float(drawdown.min())


def performance_summary(returns: pd.Series, periods_per_year: int = 12) -> dict[str, float]:
    ret = pd.to_numeric(returns, errors="coerce").dropna()
    if ret.empty:
        return {}
    annual_return = (1.0 + ret).prod() ** (periods_per_year / len(ret)) - 1.0
    annual_vol = ret.std(ddof=1) * math.sqrt(periods_per_year)
    sharpe = ret.mean() * periods_per_year / annual_vol if annual_vol > 0 else float("nan")
    mdd = max_drawdown(ret)
    return {
        "annual_return": float(annual_return),
        "annual_volatility": float(annual_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(mdd),
        "calmar": float(annual_return / abs(mdd)) if mdd < 0 else float("nan"),
        "win_rate": float((ret > 0).mean()),
        "observations": float(len(ret)),
    }

