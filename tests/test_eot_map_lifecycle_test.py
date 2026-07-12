import numpy as np
import pandas as pd

from src.factor_lifecycle.lifecycle import map_weekly_signal_to_rebalance, normalized_nonnegative_weights
from src.factor_lifecycle_test.eot_map_two_sample import (
    _multiplier_weights,
    compute_eot_barycentric_map,
    compute_eot_map_test_statistic,
    decompose_map_statistic_by_coordinate,
    robust_scale_from_base,
    sample_uniform_unit_ball,
    signed_coordinate_diagnostics,
    weighted_eot_map_bootstrap,
)
from src.factor_lifecycle_test.metric_registry import metric_directions
from src.factor_lifecycle_test.monitoring import add_persistence, benjamini_hochberg, test_based_penalty as make_test_penalty


def test_reference_points_are_in_unit_ball_and_reproducible():
    a = sample_uniform_unit_ball(100, 3, 7)
    b = sample_uniform_unit_ball(100, 3, 7)
    assert np.all(np.linalg.norm(a, axis=1) <= 1 + 1e-12)
    assert np.array_equal(a, b)


def test_weights_and_barycentric_map_shape():
    rng = np.random.default_rng(1); u = sample_uniform_unit_ball(12, 3, 2); x = rng.normal(size=(20, 3))
    weights = np.arange(1, 21, dtype=float)
    mapped, _, diagnostics = compute_eot_barycentric_map(u, x, .2, weights, return_diagnostics=True)
    assert mapped.shape == u.shape
    assert np.isclose(diagnostics["target_weights"].sum(), 1)


def test_statistic_scaling_and_recent_minus_base_direction():
    base, recent = np.zeros((5, 2)), np.ones((5, 2))
    assert np.isclose(compute_eot_map_test_statistic(base, recent, 8, 4), (8 * 4 / 12) * 2)
    difference = recent - base
    assert np.all(difference > 0)


def test_coordinate_statistics_and_ratios_sum_to_total():
    diff = np.array([[1., 2., 3.], [2., 2., 1.]])
    rows = decompose_map_statistic_by_coordinate(diff, 10, 5, ["a", "b", "c"])
    assert np.isclose(sum(x["coordinate_statistic"] for x in rows), (10 * 5 / 15) * np.mean(np.sum(diff**2, axis=1)))
    assert np.isclose(sum(x["coordinate_contribution_ratio"] for x in rows), 1)


def test_base_only_scaling_ignores_recent_when_estimating_parameters():
    base = np.arange(30, dtype=float).reshape(10, 3)
    _, _, one = robust_scale_from_base(base, np.ones((4, 3)) * 100)
    _, _, two = robust_scale_from_base(base, np.ones((4, 3)) * -100)
    assert np.array_equal(one["metric_center"], two["metric_center"])
    assert np.array_equal(one["metric_scale"], two["metric_scale"])


def test_metric_direction_and_signed_deterioration():
    diff = np.array([[-1., 1.], [-2., 2.]])
    rows = signed_coordinate_diagnostics(diff, ["rank_ic", "factor_turnover"], metric_directions(["rank_ic", "factor_turnover"]))
    assert rows[0]["improvement_or_deterioration"] == "deterioration"
    assert rows[1]["improvement_or_deterioration"] == "deterioration"


def test_fdr_and_persistence_rule():
    q = benjamini_hochberg([.01, .03, .8])
    assert np.all((q >= 0) & (q <= 1)) and q[0] <= q[1] <= q[2]
    p = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=3), "factor_name": "f", "reject_fdr": [True, False, True]})
    out = add_persistence(p)
    assert out.persistent_warning.tolist() == [False, False, True]


def test_block_multiplier_has_constant_blocks_and_normalizes():
    w = _multiplier_weights(np.random.default_rng(2), 10, "block_multiplier", 4)
    assert np.isclose(w.sum(), 1) and np.allclose(w[:4], w[0]) and np.allclose(w[4:8], w[4])


def test_bootstrap_is_centered_under_fixed_weights(monkeypatch):
    import src.factor_lifecycle_test.eot_map_two_sample as module
    rng=np.random.default_rng(3); u=sample_uniform_unit_ball(8,2,3); x=rng.normal(size=(12,2)); y=rng.normal(size=(7,2))
    mb=compute_eot_barycentric_map(u,x,.3); mr=compute_eot_barycentric_map(u,y,.3)
    monkeypatch.setattr(module, "_multiplier_weights", lambda rng, n, method, block: np.full(n, 1 / n))
    result=weighted_eot_map_bootstrap(u,x,y,mb,mr,.3,3,5)
    assert len(result["bootstrap_statistics"]) == 3 and np.allclose(result["bootstrap_statistics"], 0, atol=1e-14)


def test_no_lookahead_weekly_monthly_mapping_and_weight_normalization():
    weekly=pd.DataFrame({"date":pd.to_datetime(["2020-01-03","2020-01-10"]),"signal":[1,2]})
    out=map_weekly_signal_to_rebalance(weekly,[pd.Timestamp("2020-01-08")])
    assert out.loc[0,"signal"] == 1 and out.loc[0,"date"] <= out.loc[0,"rebalance_date"]
    assert np.isclose(normalized_nonnegative_weights(pd.Series([-1.,2.,3.])).sum(),1)


def test_penalty_is_clipped_and_zero_significance_has_no_penalty():
    p=make_test_penalty(pd.Series([.2,0]),pd.Series([1.,1.]),gamma=.5)
    assert p.iloc[0] == 1 and .5 <= p.iloc[1] <= 1
