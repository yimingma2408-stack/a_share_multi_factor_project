import pandas as pd

from scripts.data.preparation.rebuild_akshare_fundamentals_with_market_cap import recalculate_factors, winsorized_zscore
from src.data.market_cap_panel import adapt_existing_market_cap


def test_adapt_existing_total_mv_converts_ten_thousand_yuan(tmp_path):
    raw = pd.DataFrame(
        {
            "trade_date": ["2024-01-02"],
            "ticker": ["sh.600000"],
            "total_mv": [123.0],
            "circ_mv": [100.0],
        }
    )
    panel, metadata = adapt_existing_market_cap(
        raw,
        tmp_path / "valuation.csv",
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-12-31"),
    )
    assert panel.loc[0, "ticker"] == "600000"
    assert panel.loc[0, "market_cap"] == 1_230_000
    assert panel.loc[0, "float_market_cap"] == 1_000_000
    assert metadata["multiplier"] == 1e4


def test_winsorized_zscore_is_cross_sectionally_standardized():
    result = winsorized_zscore(pd.Series([1.0, 2.0, 3.0, 1000.0]))
    assert abs(result.mean()) < 1e-12
    assert abs(result.std(ddof=0) - 1.0) < 1e-12


def test_recalculate_factors_builds_cross_sectional_value_composite():
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31"] * 3),
            "market_cap": [100.0, 200.0, 300.0],
            "equity_parent": [50.0, 60.0, 70.0],
            "total_equity": [50.0, 60.0, 70.0],
            "net_profit_parent_ttm": [10.0, 12.0, 14.0],
            "net_profit_ttm": [10.0, 12.0, 14.0],
            "revenue_ttm": [80.0, 90.0, 100.0],
            "operating_cash_flow_ttm": [8.0, 9.0, 10.0],
            "total_assets": [100.0, 120.0, 140.0],
            "gross_profit_ttm": [40.0, 45.0, 50.0],
            "revenue_growth_yoy": [0.1, 0.2, 0.3],
            "earnings_growth_yoy": [0.2, 0.3, 0.4],
        }
    )
    result = recalculate_factors(panel)
    assert result[["bp", "ep", "sp", "cfp", "value_composite_raw"]].notna().all().all()
    assert abs(result["value_composite_raw"].mean()) < 1e-12
