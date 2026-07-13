"""Current-state project audit; intentionally distinguishes complete, conditional and incomplete evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports/completion_audit"


@dataclass(frozen=True)
class Requirement:
    section: str
    requirement: str
    evidence_paths: tuple[str, ...]
    status: str
    notes: str


def exists(relative: str) -> bool:
    return (ROOT / relative).exists()


def broad_fundamental_status() -> tuple[str, str]:
    path = ROOT / "data/processed/coverage_expansion/fundamental_panel_broad.parquet"
    if not path.exists():
        return "incomplete", "Broad fundamental panel is absent."
    panel = pd.read_parquet(path, columns=["ticker", "available_date", "date", "industry_pit_safe"])
    future = int((pd.to_datetime(panel["available_date"]) > pd.to_datetime(panel["date"])).sum())
    tickers = panel["ticker"].astype(str).nunique()
    industry_safe = float(panel["industry_pit_safe"].fillna(False).mean())
    if future == 0 and tickers >= 500 and industry_safe < 0.95:
        return "conditional", f"{tickers} tickers and zero future-date violations, but PIT-safe industry coverage is {industry_safe:.2%}; exclude from headline formal allocation."
    if future == 0 and tickers >= 500:
        return "complete", f"{tickers} tickers with zero future-date violations and PIT-safe industry coverage {industry_safe:.2%}."
    return "incomplete", f"Ticker breadth={tickers}, future-date violations={future}, PIT-safe industry coverage={industry_safe:.2%}."


def collect_requirements() -> list[Requirement]:
    fundamental_status, fundamental_notes = broad_fundamental_status()
    formal_complete = all(exists(path) for path in (
        "data/processed/eot_factor_lifecycle_test/eot_map_test_panel.parquet",
        "data/processed/eot_factor_lifecycle_test/eot_map_coordinate_diagnostics.parquet",
        "reports/eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md",
        "reports/eot_factor_lifecycle_test/formal_eot_delivery_audit.md",
    ))
    package_complete = all(exists(path) for path in ("pyproject.toml", "requirements.txt", "requirements-lock.txt", "environment.yml"))
    return [
        Requirement("data", "Dynamic HS300 adjusted market panel", ("data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet",), "complete" if exists("data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet") else "incomplete", "Dynamic market panel is the headline research universe."),
        Requirement("data", "Broad PIT financial, industry and market-cap panel for headline multifactor allocation", ("data/processed/coverage_expansion/fundamental_panel_broad.parquet", "reports/data_quality/point_in_time_coverage_audit.md"), fundamental_status, fundamental_notes),
        Requirement("factors", "Price/volume factor research", ("src/factors/price_volume.py", "reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md"), "complete" if exists("src/factors/price_volume.py") else "incomplete", "Price/volume factors are the current headline factor universe."),
        Requirement("factors", "Value/quality/growth factors in headline formal multifactor allocation", ("src/factors/value.py", "src/factors/quality_growth_risk.py", "reports/data_quality/point_in_time_coverage_audit.md"), "conditional" if fundamental_status == "conditional" else "incomplete", "Implementations and broad research data exist, but PIT-safe industry history prevents headline promotion."),
        Requirement("lifecycle", "Formal EOT-map two-sample lifecycle diagnostics", ("src/factor_lifecycle_test/eot_map_two_sample.py", "data/processed/eot_factor_lifecycle_test/eot_map_test_panel.parquet", "reports/eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md"), "complete" if formal_complete else "incomplete", "Formal common-reference maps, scaled statistic, 300-draw centered IID/block calibration, FDR and lifecycle outputs."),
        Requirement("portfolio", "Walk-forward allocation and transaction-cost comparison", ("data/processed/eot_factor_lifecycle_test/backtest_nav_test_based.parquet", "reports/eot_factor_lifecycle_test/backtest_summary_test_based.csv"), "complete" if exists("data/processed/eot_factor_lifecycle_test/backtest_nav_test_based.parquet") else "incomplete", "Completed as an experimental monitoring-extension comparison; not evidence of live alpha."),
        Requirement("reproducibility", "Installable, dependency-pinned environment and explicit formal-EOT cache policy", ("pyproject.toml", "requirements-lock.txt", "environment.yml", "scripts/run_full_research_pipeline.py"), "complete" if package_complete else "incomplete", "`--full --formal-eot reuse|rerun|skip` explicitly controls final formal EOT handling."),
        Requirement("engineering", "Current-state tests and formal artifact audit", ("tests/test_eot_map_lifecycle_test.py", "tests/test_data_quality_and_attribution.py", "scripts/audit_formal_eot_delivery.py"), "complete" if exists("scripts/audit_formal_eot_delivery.py") else "incomplete", "Run `pytest` and `python scripts/audit_formal_eot_delivery.py` in the installed environment."),
    ]


def write_report(requirements: list[Requirement]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([asdict(item) for item in requirements])
    frame.to_csv(REPORT_DIR / "outline_completion_audit.csv", index=False)
    counts = frame["status"].value_counts().to_dict()
    lines = [
        "# A-Share Multifactor Current-State Audit",
        "",
        "This audit is a current filesystem check, not a historical completion claim.",
        "",
        f"- Complete: {counts.get('complete', 0)}",
        f"- Conditional: {counts.get('conditional', 0)}",
        f"- Incomplete: {counts.get('incomplete', 0)}",
        "",
        "| section | status | requirement | evidence | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in requirements:
        paths = "; ".join(f"`{path}`" for path in item.evidence_paths)
        lines.append(f"| {item.section} | {item.status} | {item.requirement} | {paths} | {item.notes} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "The formal EOT-map lifecycle project is complete for the ten price/volume factors. Broad financial research inputs remain conditional and are deliberately excluded from headline formal allocation until dated PIT-safe industry history is available. Legacy distance-based EOT reports are retained as baselines, not as formal hypothesis-test evidence.",
    ])
    (REPORT_DIR / "outline_completion_audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    requirements = collect_requirements()
    write_report(requirements)
    print(pd.DataFrame([asdict(item) for item in requirements])[["section", "status", "requirement"]].to_string(index=False))


if __name__ == "__main__":
    main()
