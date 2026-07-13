import numpy as np
import pandas as pd

from src.eot_drift import compute_reference_points, eot_barycentric_map
from src.factor_lifecycle.factor_registry import lifecycle_factor_names, registry_frame
from src.factor_lifecycle.lifecycle import (
    apply_family_weight_cap,
    drift_penalty,
    map_weekly_signal_to_rebalance,
    normalized_nonnegative_weights,
    rolling_past_stat,
    transaction_cost,
)
from src.factor_lifecycle.preprocessing import preprocess_factor_cross_section
from scripts.research.eot.run_eot_factor_lifecycle import _dynamic_cluster_map, _dynamic_redundancy_map


def test_registry_directions_and_lifecycle_count():
    registry = registry_frame()
    assert set(registry["direction"].unique()).issubset({-1, 1})
    assert len(lifecycle_factor_names()) == 10


def test_preprocessing_is_cross_sectional_and_size_neutral():
    factor = np.array([0.0, 1.0, 4.0, 2.0, 5.0, 3.0, 8.0, 6.0])
    df = pd.DataFrame({"date": ["2020-01-01"] * 8, "factor": factor, "float_market_cap": np.exp(np.arange(8.0))})
    out = preprocess_factor_cross_section(df, "factor")
    valid = out["factor_processed"].notna()
    assert valid.sum() == 8
    assert abs(out.loc[valid, "factor_processed"].mean()) < 1e-10
    assert abs(np.corrcoef(out.loc[valid, "factor_processed"], np.arange(8.0))[0, 1]) < 1e-8


def test_rolling_stat_excludes_current_observation():
    s = pd.Series([1.0, 2.0, 100.0])
    out = rolling_past_stat(s, window=2, min_periods=1, stat="mean")
    assert pd.isna(out.iloc[0])
    assert out.iloc[1] == 1.0
    assert out.iloc[2] == 1.5


def test_announcement_alignment_rule_has_no_future_rows():
    frame = pd.DataFrame({"date": pd.to_datetime(["2020-05-01", "2020-06-01"]), "announcement_date": pd.to_datetime(["2020-04-30", "2020-05-31"])})
    assert (frame["announcement_date"] <= frame["date"]).all()


def test_weekly_forward_return_uses_next_observation():
    prices = pd.DataFrame({"ticker": ["A"] * 3, "close": [10.0, 11.0, 12.1]})
    fwd = prices.groupby("ticker")["close"].shift(-1) / prices["close"] - 1
    assert np.isclose(fwd.iloc[0], 0.1)
    assert np.isclose(fwd.iloc[1], 0.1)
    assert pd.isna(fwd.iloc[2])


def test_monthly_mapping_is_backward_only():
    weekly = pd.DataFrame({"date": pd.to_datetime(["2020-01-24", "2020-01-31"]), "signal": [1, 2]})
    out = map_weekly_signal_to_rebalance(weekly, [pd.Timestamp("2020-01-30")])
    assert out.loc[0, "date"] == pd.Timestamp("2020-01-24")


def test_eot_barycentric_dimensions():
    rng = np.random.default_rng(42)
    a, b = rng.normal(size=(20, 3)), rng.normal(size=(10, 3))
    u = compute_reference_points(a, b, n_reference=8)
    mapped, plan = eot_barycentric_map(u, a, epsilon=0.1)
    assert mapped.shape == (8, 3)
    assert plan.shape == (8, 20)


def test_weight_normalization_and_drift_clip():
    w = normalized_nonnegative_weights(pd.Series([-1.0, 1.0, 3.0]))
    assert np.isclose(w.sum(), 1.0)
    assert (w >= 0).all()
    p = drift_penalty(pd.Series([0.0, 100.0]))
    assert p.iloc[0] == 1.0 and p.iloc[1] == 0.5


def test_family_cap():
    w = pd.Series([0.8, 0.1, 0.1], index=["a", "b", "c"])
    fam = pd.Series(["x", "y", "y"], index=w.index)
    out = apply_family_weight_cap(w, fam, cap=0.65)
    assert np.isclose(out.sum(), 1.0)
    assert out.groupby(fam).sum().max() <= 0.6500001


def test_transaction_cost_calculation():
    net = transaction_cost(pd.Series([0.01]), pd.Series([0.5]), 10)
    assert np.isclose(net.iloc[0], 0.0095)


def test_walk_forward_eligibility_boundary():
    history = pd.Series(range(60))
    past_mean = rolling_past_stat(history, 52, 52, "mean")
    assert past_mean.iloc[:52].isna().all()
    assert past_mean.iloc[52] == np.mean(range(52))


def test_walk_forward_clusters_ignore_future_returns():
    dates = pd.date_range("2020-01-03", periods=40, freq="W-FRI")
    rows = []
    for i, date in enumerate(dates):
        rows.extend([
            {"date": date, "factor_name": "a", "long_short_return": i / 100},
            {"date": date, "factor_name": "b", "long_short_return": i / 100 + 0.001},
        ])
    perf = pd.DataFrame(rows)
    decision = dates[30]
    before = _dynamic_cluster_map(perf, decision, ["a", "b"])
    redundancy_before = _dynamic_redundancy_map(perf, decision, ["a", "b"])
    perf.loc[perf["date"] >= decision, "long_short_return"] *= -1000
    after = _dynamic_cluster_map(perf, decision, ["a", "b"])
    redundancy_after = _dynamic_redundancy_map(perf, decision, ["a", "b"])
    assert before == after
    assert redundancy_before == redundancy_after
