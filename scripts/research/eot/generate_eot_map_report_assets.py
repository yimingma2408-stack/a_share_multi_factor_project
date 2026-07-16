from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
REPORT = ROOT / "reports/eot_factor_lifecycle_test"
FIGURES = REPORT / "figures"


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIGURES / name, dpi=160, bbox_inches="tight")
    plt.close()


def make_factor_rejection_chart() -> None:
    rates = pd.Series(
        {
            "turnover_1m": 0.332,
            "volatility_3m": 0.332,
            "volatility_1m": 0.317,
            "turnover_3m": 0.316,
            "momentum_3m": 0.294,
        }
    ).sort_values()
    ax = rates.mul(100).plot.barh(figsize=(8.5, 4.5), color=sns.color_palette("deep")[0])
    ax.set(title="Highest block-bootstrap rejection rates", xlabel="Raw rejection rate (%)", ylabel="")
    ax.bar_label(ax.containers[0], fmt="%.1f%%", padding=3)
    ax.set_xlim(0, max(rates.mul(100)) * 1.18)
    save("15_factor_rejection_rates.png")


def make_coordinate_chart() -> None:
    frame = pd.DataFrame(
        {
            "metric": ["Rank IC", "Long-short return", "Downside return"],
            "Largest change": [197, 787, 2181],
            "Dominant deterioration": [725, 876, 1564],
        }
    ).set_index("metric")
    ax = frame.plot.bar(figsize=(9, 4.8), color=sns.color_palette("deep")[:2], rot=0)
    ax.set(title="Which coordinate drives the detected change?", xlabel="", ylabel="Factor-date tests")
    for container in ax.containers:
        ax.bar_label(container, fmt="%d", padding=2)
    ax.legend(frameon=False)
    save("16_coordinate_diagnostic_counts.png")


def make_lifecycle_chart() -> None:
    counts = pd.Series(
        {"Healthy": 1126, "Watch": 950, "Decaying": 220, "Recovering": 364, "Dormant": 505}
    ).sort_values()
    ax = counts.plot.barh(figsize=(8.5, 4.5), color=sns.color_palette("deep")[2])
    ax.set(title="Test-based lifecycle state distribution", xlabel="Factor-date observations", ylabel="")
    ax.bar_label(ax.containers[0], fmt="%d", padding=3)
    ax.set_xlim(0, max(counts) * 1.15)
    save("17_lifecycle_state_counts.png")


def make_backtest_chart() -> None:
    summary = pd.read_csv(REPORT / "backtest_summary_test_based.csv")
    at10 = summary[summary["cost_bps"].eq(10)].sort_values("sharpe")
    labels = {
        "equal_eligible": "Equal",
        "icir_weighting": "ICIR",
        "old_distance_eot": "Old distance",
        "formal_significance_penalty": "Formal significance",
        "formal_signed_penalty": "Formal signed",
        "test_lifecycle_filter": "Lifecycle filter",
        "test_lifecycle_filter_conservative": "Conservative filter",
    }
    values = at10.set_index("strategy")["sharpe"].rename(index=labels)
    positive, negative = sns.color_palette("deep")[2], sns.color_palette("deep")[3]
    colors = [positive if value >= 0 else negative for value in values]
    ax = values.plot.barh(figsize=(9, 5), color=colors)
    ax.axvline(0, color="0.35", linewidth=1)
    ax.set(title="Walk-forward Sharpe after 10 bps", xlabel="Annual return / annual volatility", ylabel="")
    ax.bar_label(ax.containers[0], fmt="%.3f", padding=3)
    ax.set_xlim(values.min() * 1.18, max(values.max() * 1.8, 0.04))
    save("18_strategy_sharpe_10bps.png")


def make_synthetic_chart() -> None:
    synthetic = pd.read_csv(REPORT / "synthetic_validation_summary.csv")
    rates = synthetic.groupby(["scenario", "bootstrap_method"])["reject"].mean().unstack()
    order = [
        "gaussian_null",
        "student_t_null",
        "mixture_null",
        "ar1_null",
        "mean_shift",
        "scale_change",
        "correlation_change",
        "rank_ic_deterioration",
        "downside_deterioration",
    ]
    rates = rates.reindex(order).mul(100)
    ax = rates.plot.bar(figsize=(11, 5), color=sns.color_palette("deep")[:2], rot=35)
    ax.axhline(5, color="0.35", linestyle="--", linewidth=1, label="5% nominal size")
    ax.set(title="Synthetic validation rejection rates", xlabel="", ylabel="Rejection rate (%)", ylim=(0, 108))
    ax.legend(frameon=False)
    save("19_synthetic_rejection_rates.png")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    make_factor_rejection_chart()
    make_coordinate_chart()
    make_lifecycle_chart()
    make_backtest_chart()
    make_synthetic_chart()
    print(f"Generated EOT report assets: {FIGURES}")


if __name__ == "__main__":
    main()
