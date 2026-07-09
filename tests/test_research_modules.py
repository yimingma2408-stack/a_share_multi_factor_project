import math

import pandas as pd

from src.analysis.ic import compute_rank_ic
from src.analysis.decay import add_forward_returns, compute_ic_decay
from src.backtest.costs import turnover_from_weights
from src.backtest.execution import add_tradable_flags, constrain_rebalance_orders, estimate_execution_costs
from src.factors.preprocess import neutralize_cross_section, zscore_series
from src.factors.price_volume import build_price_volume_factor_panel
from src.factors.quality_growth_risk import build_quality_growth_factors, build_rolling_risk_factors


def test_price_volume_factor_panel_adds_core_columns():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=80).tolist() * 2,
            "ticker": ["000001"] * 80 + ["000002"] * 80,
            "close": list(range(10, 90)) + list(range(20, 100)),
            "amount": [1000.0] * 160,
            "turnover": [1.0] * 160,
        }
    )
    out = build_price_volume_factor_panel(df)
    assert {"ret_1d", "mom_60_20d", "reversal_20d", "lowvol_20d", "lowturn_20d"}.issubset(out.columns)


def test_zscore_series_standardizes_nonconstant_input():
    z = zscore_series(pd.Series([1.0, 2.0, 3.0]))
    assert abs(z.mean()) < 1e-12
    assert math.isclose(z.std(ddof=0), 1.0)


def test_neutralize_cross_section_removes_size_slope():
    frame = pd.DataFrame({"factor": [1.0, 2.0, 3.0, 4.0, 5.0], "size": [1, 2, 3, 4, 5]})
    resid = neutralize_cross_section(frame, "factor", size_col="size")
    assert resid.notna().sum() == 5
    assert abs(resid.mean()) < 1e-10


def test_compute_rank_ic_returns_rows():
    df = pd.DataFrame(
        {
            "date": ["2020-01-31"] * 40,
            "factor": range(40),
            "fwd_ret": range(40),
        }
    )
    out = compute_rank_ic(df, ["factor"], "fwd_ret")
    assert len(out) == 1
    assert out.loc[0, "rank_ic"] == 1.0


def test_compute_ic_decay_returns_horizon_rows():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=50).tolist() * 2,
            "ticker": ["A"] * 50 + ["B"] * 50,
            "close": list(range(10, 60)) + list(range(20, 70)),
            "factor": list(range(50)) + list(range(50)),
        }
    )
    out = add_forward_returns(df, horizons=(1, 5))
    decay = compute_ic_decay(out, ["factor"], horizons=(1, 5), min_obs=2)
    assert set(decay["horizon_days"]) == {1, 5}


def test_turnover_from_weights():
    weights = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-01-31", "2020-02-29", "2020-02-29"],
            "ticker": ["A", "B", "A", "C"],
            "weight": [0.5, 0.5, 0.25, 0.75],
        }
    )
    out = turnover_from_weights(weights)
    assert out.loc[0, "turnover"] == 0.5
    assert out.loc[1, "turnover"] == 0.75


def test_add_tradable_flags_blocks_limit_up_buy():
    df = pd.DataFrame({"pct_change": [10.0, -10.0, 0.0], "trade_status": [1, 1, 0], "is_st": [0, 0, 0]})
    out = add_tradable_flags(df)
    assert bool(out.loc[0, "can_buy"]) is False
    assert bool(out.loc[1, "can_sell"]) is False
    assert bool(out.loc[2, "can_hold"]) is False


def test_constrain_rebalance_orders_blocks_untradable_buy():
    target = pd.DataFrame({"date": ["2020-01-31"], "ticker": ["A"], "weight": [1.0]})
    tradability = pd.DataFrame({"date": ["2020-01-31"], "ticker": ["A"], "can_buy": [False], "can_sell": [True]})
    out = constrain_rebalance_orders(target, tradability=tradability)
    assert bool(out.loc[0, "blocked_trade"]) is True
    assert out.loc[0, "executed_weight"] == 0.0


def test_estimate_execution_costs_adds_cost_components():
    trades = pd.DataFrame({"trade_value": [1000000.0], "adv": [10000000.0]})
    out = estimate_execution_costs(trades, spread_bps=4.0, slippage_bps=6.0, impact_bps_at_100pct_adv=50.0)
    assert out.loc[0, "spread_cost"] == 200.0
    assert out.loc[0, "slippage_cost"] == 600.0
    assert out.loc[0, "market_impact_cost"] > 0
    assert out.loc[0, "execution_cost"] > 800.0


def test_quality_growth_factors_add_core_columns():
    rows = []
    for i in range(8):
        rows.append(
            {
                "date": pd.Timestamp("2020-01-31") + pd.offsets.MonthEnd(i),
                "ticker": "000001",
                "report_date": pd.Timestamp("2018-12-31") + pd.offsets.QuarterEnd(i),
                "announcement_date": pd.Timestamp("2019-01-31") + pd.offsets.QuarterEnd(i),
                "book_equity": 100.0,
                "total_assets": 200.0,
                "net_profit": 10.0 + i,
                "revenue": 100.0 + 10.0 * i,
                "gross_profit": 40.0 + i,
                "operating_cash_flow": 20.0 + i,
                "market_cap": 500.0,
            }
        )
    out = build_quality_growth_factors(pd.DataFrame(rows))
    assert {"size", "roe", "gross_profitability", "ocf_to_assets", "revenue_growth", "earnings_growth"}.issubset(
        out.columns
    )
    assert out["revenue_growth"].notna().sum() > 0


def test_rolling_risk_factors_add_core_columns():
    dates = pd.date_range("2020-01-01", periods=140)
    df = pd.DataFrame(
        {
            "date": dates.tolist() * 2,
            "ticker": ["A"] * 140 + ["B"] * 140,
            "return_1d": [0.001 * ((i % 5) - 2) for i in range(140)]
            + [0.0015 * ((i % 7) - 3) for i in range(140)],
        }
    )
    out = build_rolling_risk_factors(df, window=60, min_periods=30)
    assert {"rolling_beta", "idiosyncratic_volatility", "downside_beta"}.issubset(out.columns)
    assert out["rolling_beta"].notna().sum() > 0
