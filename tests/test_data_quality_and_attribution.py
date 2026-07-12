import numpy as np
import pandas as pd

from src.analysis.attribution import industry_weight_exposure, market_model_regression, portfolio_exposure
from src.data.coarse_industry import build_coarse_industry_panel, map_industry_label
from src.data.float_cap_proxy import build_float_cap_proxy_panel
from src.data.pit_audit import audit_point_in_time_coverage
from src.evaluation.metrics import max_drawdown, performance_summary
from src.factor_lifecycle_test.workflow import (
    attach_latest_monthly_weights,
    month_end_signals,
    rolling_quality_features,
)


def test_pit_audit_excludes_latest_snapshot_industry_and_detects_future_dates():
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31", "2024-02-29"]),
            "ticker": ["000001", "000001"],
            "available_date": pd.to_datetime(["2024-01-15", "2024-03-01"]),
            "industry_pit_safe": [False, False],
            "float_market_cap_used": [1.0, 1.0],
        }
    )
    audit = audit_point_in_time_coverage(panel, "test")
    assert audit.future_available_date_violations == 1
    assert not audit.usable_for_formal_multifactor
    assert "industry" in audit.formal_exclusion_reason


def test_industry_snapshot_is_explicitly_not_pit_safe():
    universe = pd.DataFrame({"date": pd.to_datetime(["2024-01-31"]), "ticker": ["000001"]})
    raw = pd.DataFrame({"ticker": ["000001"], "industry": ["银行"], "update_date": ["2025-01-01"]})
    panel = build_coarse_industry_panel(universe, raw)
    assert panel.loc[0, "industry_coarse"] == "financials"
    assert not panel.loc[0, "industry_pit_safe"]
    assert map_industry_label("半导体") == "information_technology"


def test_float_cap_proxy_preserves_observed_and_flags_fallbacks():
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31"] * 3),
            "ticker": ["A", "B", "C"],
            "market_cap": [100.0, 200.0, 300.0],
            "float_market_cap": [50.0, np.nan, np.nan],
            "industry_coarse": ["financials"] * 3,
        }
    )
    result = build_float_cap_proxy_panel(panel, min_group_obs=3)
    assert result.loc[0, "market_cap_quality_grade"] == "A"
    assert result.loc[1:, "float_market_cap_used"].notna().all()
    assert result.loc[1:, "float_market_cap_is_proxy"].all()


def test_attribution_and_metrics_outputs_are_well_defined():
    returns = pd.DataFrame({"portfolio_return": np.arange(12) * 0.01 + 0.001, "benchmark_return": np.arange(12) * 0.01})
    regression = market_model_regression(returns)
    assert regression["observations"] == 12
    holdings = pd.DataFrame({"date": ["2024-01-31", "2024-01-31"], "ticker": ["A", "B"], "weight": [0.4, 0.6]})
    exposure = pd.DataFrame({"date": ["2024-01-31", "2024-01-31"], "ticker": ["A", "B"], "size": [1.0, 3.0]})
    assert np.isclose(portfolio_exposure(holdings, exposure, ["size"]).loc[0, "size"], 2.2)
    industry = pd.DataFrame({"date": ["2024-01-31", "2024-01-31"], "ticker": ["A", "B"], "industry": ["x", "y"]})
    assert industry_weight_exposure(holdings, industry)["portfolio_weight"].sum() == 1.0
    assert max_drawdown(pd.Series([0.1, -0.2, 0.1])) < 0
    assert performance_summary(pd.Series([0.01, -0.01, 0.02]))["observations"] == 3.0


def test_workflow_helpers_remain_past_only():
    perf = pd.DataFrame({"date": pd.date_range("2020-01-03", periods=60, freq="W-FRI"), "factor_name": "f", "rank_ic": np.arange(60, dtype=float)})
    quality = rolling_quality_features(perf, base_window=20, recent_window=10)
    assert pd.isna(quality.loc[0, "historical_icir"])
    signals = month_end_signals(pd.DataFrame({"date": pd.to_datetime(["2020-01-03", "2020-01-31", "2020-02-07"]), "factor_name": ["f"] * 3}))
    assert signals.date.tolist() == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-07")]
    dashboard = pd.DataFrame({"date": pd.to_datetime(["2020-01-31", "2020-02-07"]), "factor_name": ["f", "f"]})
    weights = pd.DataFrame({"date": pd.to_datetime(["2020-01-31"]), "factor_name": ["f"], "final_weight": [0.7]})
    attached = attach_latest_monthly_weights(dashboard, weights)
    assert attached.final_weight.tolist() == [0.7, 0.7]
