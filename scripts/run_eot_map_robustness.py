from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.factor_lifecycle_test.eot_map_two_sample import run_eot_map_two_sample_test
from src.factor_lifecycle_test.metric_registry import EOT_METRIC_NAMES

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/eot_factor_lifecycle/weekly_factor_performance_full.parquet"
OUTPUT = ROOT / "reports/eot_factor_lifecycle_test/parameter_robustness_summary.csv"


def main() -> None:
    perf = pd.read_parquet(SOURCE).sort_values("date")
    rows = []
    for fi, (factor, g) in enumerate(perf.groupby("factor_name")):
        values = g[list(EOT_METRIC_NAMES)].dropna().to_numpy(float)
        base, recent = values[-182:-26], values[-26:]
        settings = []
        settings += [(n, .2, "iid_multiplier", None, "reference_size") for n in (50, 100, 200)]
        settings += [(100, e, "iid_multiplier", None, "epsilon") for e in (.1, .2, .5)]
        settings += [(100, .2, "block_multiplier", b, "block_length") for b in (4, 8, 13)]
        for si, (nref, eps, method, block, family) in enumerate(settings):
            result = run_eot_map_two_sample_test(
                base, recent, n_reference=nref, epsilon_scale=eps, n_bootstrap=100,
                random_state=42 + 100 * fi + si, bootstrap_method=method, block_length=block,
            )
            rows.append({"factor_name": factor, "setting_family": family, "n_reference": nref,
                "epsilon_scale": eps, "bootstrap_method": method, "block_length": block,
                "test_statistic": result["test_statistic"], "p_value": result["p_value"],
                "reject": result["reject_raw"], "sinkhorn_status": result["sinkhorn_status"]})
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    print(f"wrote {len(rows)} robustness rows")


if __name__ == "__main__":
    main()
