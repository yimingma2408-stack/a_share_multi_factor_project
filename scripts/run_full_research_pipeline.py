from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the full research pipeline from cached raw data. Use this inside the quant environment.",
    )
    args = parser.parse_args()

    run([sys.executable, "scripts/run_smoke_factor_report.py"])
    if args.full:
        run([sys.executable, "scripts/run_eot_factor_drift_feasibility.py"])
        run([sys.executable, "scripts/run_weekly_eot_factor_drift.py"])
        run([sys.executable, "scripts/run_weekly_eot_drift_robustness.py"])
        run([sys.executable, "scripts/download_fundamentals_akshare.py", "--build-only"])
        run([sys.executable, "scripts/run_value_neutralized_factor_research.py"])
        run([sys.executable, "scripts/run_quality_growth_risk_factor_research.py"])
        run([sys.executable, "scripts/run_final_factor_research_report.py"])
    run([sys.executable, "scripts/run_outline_completion_audit.py"])
    print()
    if args.full:
        print("Full cached-data pipeline complete.")
    else:
        print("Lightweight pipeline complete.")
        print("For the full cached-data pipeline, use the quant environment and run:")
        print("  /opt/anaconda3/bin/conda run -n quant python scripts/run_full_research_pipeline.py --full")
    print("See reports/completion_audit/outline_completion_audit.md for the current requirement-by-requirement state.")


if __name__ == "__main__":
    main()
