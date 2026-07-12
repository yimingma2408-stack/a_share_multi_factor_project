from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "reports/eot_factor_lifecycle_test/current_eot_implementation_audit.md",
    "reports/eot_factor_lifecycle_test/metric_registry.csv",
    "src/factor_lifecycle_test/metric_registry.py",
    "src/factor_lifecycle_test/eot_map_two_sample.py",
    "data/processed/eot_factor_lifecycle_test/eot_map_test_panel.parquet",
    "data/processed/eot_factor_lifecycle_test/eot_map_coordinate_diagnostics.parquet",
    "data/processed/eot_factor_lifecycle_test/factor_lifecycle_states_test_based.parquet",
    "data/processed/eot_factor_lifecycle_test/factor_test_dashboard.parquet",
    "data/processed/eot_factor_lifecycle_test/factor_weights_test_based.parquet",
    "data/processed/eot_factor_lifecycle_test/backtest_nav_test_based.parquet",
    "reports/eot_factor_lifecycle_test/backtest_summary_test_based.csv",
    "reports/eot_factor_lifecycle_test/transaction_cost_sensitivity_test_based.csv",
    "reports/eot_factor_lifecycle_test/synthetic_validation_summary.csv",
    "reports/eot_factor_lifecycle_test/bootstrap_calibration_report.md",
    "reports/eot_factor_lifecycle_test/computational_diagnostics.csv",
    "reports/eot_factor_lifecycle_test/test_report.md",
    "reports/eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md",
    "reports/eot_factor_lifecycle_test/README.md",
]

PANEL_COLUMNS = {
    "date", "factor_name", "factor_family", "n_base", "n_recent", "n_reference", "epsilon",
    "epsilon_scale", "test_statistic", "unscaled_map_distance", "bootstrap_critical_value_iid",
    "bootstrap_critical_value_block", "p_value_iid", "p_value_block", "q_value_cross_factor",
    "reject_iid", "reject_block", "reject_fdr", "persistent_warning", "sinkhorn_status",
    "bootstrap_status", "block_length", "dominant_change_metric", "dominant_deterioration_metric",
    "total_deterioration_score", "notes",
}

COORD_COLUMNS = {
    "date", "factor_name", "metric_name", "coordinate_statistic", "coordinate_contribution_ratio",
    "signed_map_displacement", "signed_improvement_score", "deterioration_score", "deterioration_share",
    "coordinate_raw_p_value", "coordinate_holm_p_value", "coordinate_bh_q_value", "coordinate_reject",
}


def main() -> None:
    failures = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.exists() or (path.is_file() and path.stat().st_size == 0):
            failures.append(f"missing/empty: {relative}")
    figures = list((ROOT / "reports/eot_factor_lifecycle_test/figures").glob("*.png"))
    if len(figures) < 14:
        failures.append(f"expected at least 14 figures, found {len(figures)}")

    panel = pd.read_parquet(ROOT / "data/processed/eot_factor_lifecycle_test/eot_map_test_panel.parquet")
    coords = pd.read_parquet(ROOT / "data/processed/eot_factor_lifecycle_test/eot_map_coordinate_diagnostics.parquet")
    missing = PANEL_COLUMNS - set(panel.columns)
    if missing:
        failures.append(f"panel columns missing: {sorted(missing)}")
    missing = COORD_COLUMNS - set(coords.columns)
    if missing:
        failures.append(f"coordinate columns missing: {sorted(missing)}")
    if not ((panel.n_base == 156) & (panel.n_recent == 26) & (panel.n_reference == 100)).all():
        failures.append("window/reference parameters are inconsistent")
    if not np.allclose(panel.test_statistic, panel.unscaled_map_distance * (156 * 26 / 182), rtol=1e-7, atol=1e-10):
        failures.append("test-statistic scaling invariant failed")
    sums = coords.groupby(["date", "factor_name"])["coordinate_statistic"].sum()
    totals = panel.set_index(["date", "factor_name"])["test_statistic"].reindex(sums.index)
    if not np.allclose(sums, totals, rtol=1e-6, atol=1e-8):
        failures.append("coordinate statistics do not sum to total")
    ratios = coords.groupby(["date", "factor_name"])["coordinate_contribution_ratio"].sum()
    if not np.allclose(ratios, 1, rtol=1e-6, atol=1e-8):
        failures.append("coordinate contribution ratios do not sum to one")
    diagnostics = pd.read_csv(ROOT / "reports/eot_factor_lifecycle_test/computational_diagnostics.csv")
    if diagnostics.n_bootstrap.min() < 300:
        failures.append(f"final bootstrap count below 300: {diagnostics.n_bootstrap.min()}")
    expected_dates = 0
    source = pd.read_parquet(ROOT / "data/processed/eot_factor_lifecycle/weekly_factor_performance_full.parquet")
    for _, g in source.groupby("factor_name"):
        expected_dates += max(len(g) - 182, 0)
    if len(panel) != expected_dates:
        failures.append(f"weekly factor-date coverage mismatch: {len(panel)} != {expected_dates}")
    if failures:
        print("TASK_711_AUDIT_FAILED")
        print("\n".join(f"- {x}" for x in failures))
        raise SystemExit(1)
    print(f"TASK_711_AUDIT_OK: {len(panel)} weekly tests, {len(coords)} coordinate rows, {len(figures)} figures")


if __name__ == "__main__":
    main()
