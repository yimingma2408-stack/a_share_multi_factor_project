from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())


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
    parser.add_argument(
        "--formal-eot",
        choices=["reuse", "rerun", "skip"],
        default="reuse",
        help="Formal EOT-map policy in --full mode: validate/reuse cached final panel, recompute it, or skip explicitly.",
    )
    parser.add_argument("--formal-bootstrap", type=int, default=300, help="Bootstrap draws used only with --formal-eot rerun.")
    parser.add_argument("--formal-references", type=int, default=100, help="Reference sample size used only with --formal-eot rerun.")
    args = parser.parse_args()

    run([sys.executable, "scripts/research/factors/run_smoke_factor_report.py"])
    if args.full:
        run([sys.executable, "scripts/research/eot/run_eot_factor_drift_feasibility.py"])
        run([sys.executable, "scripts/research/eot/run_weekly_eot_factor_drift.py"])
        run([sys.executable, "scripts/research/eot/run_weekly_eot_drift_robustness.py"])
        run([sys.executable, "scripts/data/acquisition/download_fundamentals_akshare.py", "--build-only"])
        run([sys.executable, "scripts/research/factors/run_value_neutralized_factor_research.py"])
        run([sys.executable, "scripts/research/factors/run_quality_growth_risk_factor_research.py"])
        run([sys.executable, "scripts/research/factors/run_final_factor_research_report.py"])
        if args.formal_eot == "reuse":
            # Reuse means validate the delivered 300-draw panel; it never silently substitutes legacy distance output.
            run([sys.executable, "scripts/audits/audit_formal_eot_delivery.py"])
        elif args.formal_eot == "rerun":
            run([
                sys.executable,
                "scripts/research/eot/run_eot_map_lifecycle_test.py",
                "--bootstrap", str(args.formal_bootstrap),
                "--references", str(args.formal_references),
            ])
        else:
            print("WARNING: formal EOT-map stage explicitly skipped; no formal lifecycle result is refreshed.")
    run([sys.executable, "scripts/audits/run_pit_coverage_audit.py"])
    run([sys.executable, "scripts/audits/run_outline_completion_audit.py"])
    print()
    if args.full:
        print(f"Full cached-data pipeline complete (formal EOT policy: {args.formal_eot}).")
    else:
        print("Lightweight pipeline complete.")
        print("For the full cached-data pipeline, use the quant environment and run:")
        print("  /opt/anaconda3/bin/conda run -n quant python scripts/workflows/run_full_research_pipeline.py --full --formal-eot reuse")
    print("See reports/completion_audit/outline_completion_audit.md for the current requirement-by-requirement state.")


if __name__ == "__main__":
    main()
