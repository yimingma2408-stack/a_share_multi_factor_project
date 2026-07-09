from __future__ import annotations

import pandas as pd


def turnover_from_weights(weights: pd.DataFrame, date_col: str = "date", ticker_col: str = "ticker") -> pd.DataFrame:
    required = {date_col, ticker_col, "weight"}
    if not required.issubset(weights.columns):
        raise ValueError(f"weights must contain {sorted(required)}")
    rows = []
    prev = pd.Series(dtype=float)
    for date, g in weights.sort_values(date_col).groupby(date_col, sort=True):
        cur = g.set_index(ticker_col)["weight"].astype(float)
        aligned = pd.concat([prev.rename("prev"), cur.rename("cur")], axis=1).fillna(0.0)
        rows.append({"date": date, "turnover": 0.5 * (aligned["cur"] - aligned["prev"]).abs().sum()})
        prev = cur
    return pd.DataFrame(rows)


def apply_linear_costs(returns: pd.DataFrame, turnover: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    out = returns.merge(turnover, on="date", how="left")
    out["cost"] = out["turnover"].fillna(0.0) * float(cost_bps) / 10000.0
    out["net_return"] = out["gross_return"] - out["cost"]
    return out

