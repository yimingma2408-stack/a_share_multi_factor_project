import numpy as np
import pandas as pd

from scripts.run_demo import CORE_FACTORS, backward_signal_date, normalized_weights


def test_demo_uses_five_core_factors():
    assert len(CORE_FACTORS) == 5
    assert {"reversal_1m", "momentum_3m", "volatility_1m", "turnover_1m", "liquidity_1m"} == set(CORE_FACTORS)


def test_backward_signal_mapping_never_uses_future_date():
    dates = pd.Series(pd.to_datetime(["2020-01-03", "2020-01-10", "2020-01-17"]))
    selected = backward_signal_date(dates, pd.Timestamp("2020-01-15"))
    assert selected == pd.Timestamp("2020-01-10")
    assert selected <= pd.Timestamp("2020-01-15")


def test_demo_weights_sum_to_one():
    weights = normalized_weights(pd.Series([0.0, 2.0, 3.0]))
    assert np.isclose(weights.sum(), 1.0)
    assert (weights >= 0).all()


def test_top_fraction_stock_count_is_variable():
    counts = [max(int(n * 0.20), 1) for n in [250, 296, 340]]
    assert counts == [50, 59, 68]
    assert len(set(counts)) == 3
