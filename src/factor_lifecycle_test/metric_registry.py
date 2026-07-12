from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class MetricSpec:
    metric_name: str
    description: str
    better_direction: int
    primary_or_auxiliary: str
    included_in_eot: bool
    scaling_method: str
    diagnostic_weight: float
    notes: str = ""


METRIC_REGISTRY = (
    MetricSpec("rank_ic", "Weekly cross-sectional Rank IC", 1, "primary", True, "base_median_mad", 1.0),
    MetricSpec("long_short_return", "Weekly top-minus-bottom factor return", 1, "primary", True, "base_median_mad", 0.75),
    MetricSpec("downside_return", "min(long_short_return, 0)", 1, "primary", True, "base_median_mad", 1.0),
    MetricSpec("factor_turnover", "Factor portfolio turnover", -1, "auxiliary", False, "base_median_mad", 0.5),
    MetricSpec("long_short_volatility", "Long-short return volatility", -1, "auxiliary", False, "base_median_mad", 0.5),
    MetricSpec("drawdown", "Factor NAV drawdown represented as a non-positive value", 1, "auxiliary", False, "base_median_mad", 0.5),
    MetricSpec("coverage_ratio", "Cross-sectional valid-observation ratio", 1, "auxiliary", False, "base_median_mad", 0.25),
    MetricSpec("ic_breadth", "Cross-sectional predictive breadth", 1, "auxiliary", False, "base_median_mad", 0.25),
)

EOT_METRIC_NAMES = tuple(x.metric_name for x in METRIC_REGISTRY if x.included_in_eot)


def metric_registry_frame() -> pd.DataFrame:
    return pd.DataFrame([asdict(x) for x in METRIC_REGISTRY])


def metric_directions(metric_names: list[str] | tuple[str, ...]) -> dict[str, int]:
    directions = {x.metric_name: x.better_direction for x in METRIC_REGISTRY}
    missing = set(metric_names) - directions.keys()
    if missing:
        raise KeyError(f"Metrics absent from registry: {sorted(missing)}")
    return {name: directions[name] for name in metric_names}
