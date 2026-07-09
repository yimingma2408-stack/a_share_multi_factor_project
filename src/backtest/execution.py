from __future__ import annotations

import numpy as np
import pandas as pd


def add_limit_flags(
    df: pd.DataFrame,
    pct_change_col: str = "pct_change",
    st_col: str | None = None,
    normal_limit: float = 9.8,
    st_limit: float = 4.8,
) -> pd.DataFrame:
    out = df.copy()
    pct = pd.to_numeric(out[pct_change_col], errors="coerce")
    if st_col and st_col in out.columns:
        is_st = out[st_col].fillna(0).astype(int).eq(1)
        limit = pd.Series(normal_limit, index=out.index).where(~is_st, st_limit)
    else:
        limit = pd.Series(normal_limit, index=out.index)
    out["is_limit_up"] = pct >= limit
    out["is_limit_down"] = pct <= -limit
    return out


def add_tradable_flags(
    df: pd.DataFrame,
    trade_status_col: str | None = "trade_status",
    st_col: str | None = "is_st",
    pct_change_col: str | None = "pct_change",
) -> pd.DataFrame:
    out = df.copy()
    if pct_change_col and pct_change_col in out.columns and "is_limit_up" not in out.columns:
        out = add_limit_flags(out, pct_change_col=pct_change_col, st_col=st_col)

    can_trade = pd.Series(True, index=out.index)
    if trade_status_col and trade_status_col in out.columns:
        can_trade &= pd.to_numeric(out[trade_status_col], errors="coerce").fillna(0).eq(1)
    if st_col and st_col in out.columns:
        can_trade &= pd.to_numeric(out[st_col], errors="coerce").fillna(0).eq(0)
    if "is_limit_up" in out.columns:
        out["can_buy"] = can_trade & ~out["is_limit_up"]
    else:
        out["can_buy"] = can_trade
    if "is_limit_down" in out.columns:
        out["can_sell"] = can_trade & ~out["is_limit_down"]
    else:
        out["can_sell"] = can_trade
    out["can_hold"] = can_trade
    return out


def constrain_rebalance_orders(
    target_weights: pd.DataFrame,
    current_weights: pd.DataFrame | None = None,
    tradability: pd.DataFrame | None = None,
    date_col: str = "date",
    ticker_col: str = "ticker",
    weight_col: str = "weight",
) -> pd.DataFrame:
    """Apply buy/sell tradability constraints to a target rebalance."""
    target = target_weights[[date_col, ticker_col, weight_col]].copy()
    target = target.rename(columns={weight_col: "target_weight"})
    if current_weights is None or current_weights.empty:
        current = target[[date_col, ticker_col]].copy()
        current["current_weight"] = 0.0
    else:
        current = current_weights[[date_col, ticker_col, weight_col]].copy()
        current = current.rename(columns={weight_col: "current_weight"})

    orders = target.merge(current, on=[date_col, ticker_col], how="outer").fillna(
        {"target_weight": 0.0, "current_weight": 0.0}
    )
    if tradability is not None and not tradability.empty:
        flags = [col for col in ["can_buy", "can_sell", "can_hold"] if col in tradability.columns]
        orders = orders.merge(tradability[[date_col, ticker_col] + flags], on=[date_col, ticker_col], how="left")
    for col in ["can_buy", "can_sell", "can_hold"]:
        if col not in orders.columns:
            orders[col] = True
        orders[col] = orders[col].fillna(False).astype(bool)

    desired_trade = orders["target_weight"] - orders["current_weight"]
    blocked_buy = (desired_trade > 0) & ~orders["can_buy"]
    blocked_sell = (desired_trade < 0) & ~orders["can_sell"]
    blocked_hold = (orders["target_weight"] > 0) & ~orders["can_hold"]
    orders["blocked_trade"] = blocked_buy | blocked_sell | blocked_hold
    orders["executed_trade_weight"] = desired_trade.where(~orders["blocked_trade"], 0.0)
    orders["executed_weight"] = orders["current_weight"] + orders["executed_trade_weight"]
    return orders


def estimate_execution_costs(
    trades: pd.DataFrame,
    trade_value_col: str = "trade_value",
    adv_col: str | None = "adv",
    spread_bps: float = 5.0,
    slippage_bps: float = 5.0,
    impact_bps_at_100pct_adv: float = 50.0,
) -> pd.DataFrame:
    """Estimate spread, slippage, and square-root market-impact costs."""
    out = trades.copy()
    trade_value = pd.to_numeric(out[trade_value_col], errors="coerce").abs().fillna(0.0)
    out["spread_cost"] = trade_value * (float(spread_bps) / 2.0) / 10000.0
    out["slippage_cost"] = trade_value * float(slippage_bps) / 10000.0

    if adv_col and adv_col in out.columns:
        adv = pd.to_numeric(out[adv_col], errors="coerce")
        participation = (trade_value / adv.where(adv > 0)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    else:
        participation = pd.Series(0.0, index=out.index)
    out["participation_rate"] = participation.clip(lower=0.0)
    impact_rate = float(impact_bps_at_100pct_adv) * np.sqrt(out["participation_rate"]) / 10000.0
    out["market_impact_cost"] = trade_value * impact_rate
    out["execution_cost"] = out["spread_cost"] + out["slippage_cost"] + out["market_impact_cost"]
    out["execution_cost_rate"] = out["execution_cost"] / trade_value.where(trade_value > 0)
    return out
