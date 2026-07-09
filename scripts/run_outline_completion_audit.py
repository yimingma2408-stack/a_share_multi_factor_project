from __future__ import annotations

from dataclasses import dataclass
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


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def any_exists(paths: tuple[str, ...]) -> bool:
    return any(exists(path) for path in paths)


def file_contains_all(path: str, needles: tuple[str, ...]) -> bool:
    full_path = ROOT / path
    if not full_path.exists():
        return False
    try:
        text = full_path.read_text(encoding="utf-8")
    except Exception:
        return False
    return all(needle in text for needle in needles)


def parquet_min_tickers(path: str, min_tickers: int) -> bool:
    full_path = ROOT / path
    if not full_path.exists():
        return False
    try:
        df = pd.read_parquet(full_path, columns=["ticker"])
    except Exception:
        return False
    return "ticker" in df.columns and df["ticker"].astype(str).nunique() >= min_tickers


def parquet_min_complete_tickers(path: str, min_tickers: int, required_columns: tuple[str, ...]) -> bool:
    full_path = ROOT / path
    if not full_path.exists():
        return False
    columns = ["ticker", *required_columns]
    try:
        df = pd.read_parquet(full_path, columns=columns)
    except Exception:
        return False
    complete = df.dropna(subset=list(required_columns))
    return complete["ticker"].astype(str).nunique() >= min_tickers


def collect_requirements() -> list[Requirement]:
    requirements: list[Requirement] = []

    def add(section: str, requirement: str, paths: tuple[str, ...], done: bool, notes: str) -> None:
        requirements.append(
            Requirement(
                section=section,
                requirement=requirement,
                evidence_paths=paths,
                status="complete" if done else "incomplete",
                notes=notes,
            )
        )

    add(
        "data",
        "HS300 or CSI500 universe and daily adjusted price/volume data",
        (
            "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet",
            "data/processed/clean_daily_data.csv",
            "reports/eot_factor_drift_feasibility/data_inventory.md",
        ),
        all(
            exists(path)
            for path in (
                "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet",
                "reports/eot_factor_drift_feasibility/data_inventory.md",
            )
        ),
        "Dynamic HS300 panel exists; current default Python cannot read parquet without pyarrow/fastparquet.",
    )
    add(
        "data",
        "Industry, market-cap, and point-in-time fundamental data",
        ("data/processed/fundamental_panel.parquet", "data/processed/industry_size_panel.parquet"),
        parquet_min_complete_tickers(
            "data/processed/fundamental_panel.parquet",
            200,
            ("market_cap", "book_equity", "net_profit", "revenue", "operating_cash_flow"),
        )
        and parquet_min_complete_tickers("data/processed/industry_size_panel.parquet", 200, ("industry", "market_cap")),
        "Required for value factors, neutralization, and attribution; must cover a broad HS300 universe, not only a smoke-test sample.",
    )
    add(
        "factors",
        "Momentum, low-volatility, turnover, and liquidity factors",
        ("src/factors/price_volume.py", "scripts/run_eot_factor_drift_feasibility.py"),
        all(exists(path) for path in ("src/factors/price_volume.py", "scripts/run_eot_factor_drift_feasibility.py")),
        "Reusable price/volume factor library and existing EOT feasibility factor script are present.",
    )
    add(
        "factors",
        "Value factors BP, EP, SP, and CFP",
        (
            "src/factors/value.py",
            "scripts/run_value_neutralized_factor_research.py",
            "data/processed/fundamental_panel.parquet",
            "reports/final/value_neutralized_factor_report.md",
        ),
        exists("src/factors/value.py")
        and exists("scripts/run_value_neutralized_factor_research.py")
        and exists("reports/final/value_neutralized_factor_report.md")
        and parquet_min_complete_tickers(
            "data/processed/fundamental_panel.parquet",
            200,
            ("market_cap", "book_equity", "net_profit", "revenue", "operating_cash_flow"),
        ),
        "Code interface and production script exist; completion requires broad point-in-time outputs and report evidence.",
    )
    add(
        "preprocess",
        "Winsorization, standardization, and industry/size neutralization",
        (
            "src/factors/preprocess.py",
            "data/processed/industry_size_panel.parquet",
            "reports/final/value_neutralized_factor_report.md",
        ),
        exists("src/factors/preprocess.py")
        and exists("reports/final/value_neutralized_factor_report.md")
        and parquet_min_complete_tickers("data/processed/industry_size_panel.parquet", 200, ("industry", "market_cap")),
        "Reusable preprocessing code exists; production completion requires broad industry/size coverage and report evidence.",
    )
    add(
        "single_factor",
        "IC/Rank IC, factor correlation, grouped return tests, and Fama-MacBeth regression",
        ("src/analysis/ic.py", "src/analysis/correlations.py", "src/analysis/grouping.py", "src/analysis/fama_macbeth.py"),
        all(
            exists(path)
            for path in (
                "src/analysis/ic.py",
                "src/analysis/correlations.py",
                "src/analysis/grouping.py",
                "src/analysis/fama_macbeth.py",
            )
        ),
        "Analysis modules are implemented and value/EOT report outputs provide full-panel evidence.",
    )
    add(
        "multifactor",
        "Equal, ICIR, and drift-aware multifactor weighting",
        (
            "scripts/run_eot_factor_drift_feasibility.py",
            "scripts/run_weekly_eot_factor_drift.py",
            "reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md",
        ),
        all(
            exists(path)
            for path in (
                "scripts/run_eot_factor_drift_feasibility.py",
                "reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md",
            )
        ),
        "Existing reports cover equal, ICIR, and EOT variants on price/volume factors.",
    )
    add(
        "portfolio",
        "Long-only top-quantile portfolio, turnover, and simple cost sensitivity",
        ("src/backtest/costs.py", "reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md"),
        all(
            exists(path)
            for path in (
                "src/backtest/costs.py",
                "reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md",
            )
        ),
        "Simple turnover/cost tools and robustness report exist.",
    )
    add(
        "portfolio",
        "Strict execution modeling: limit-up/limit-down, suspension, slippage, spread, and market impact",
        ("src/backtest/execution.py", "src/backtest/costs.py", "reports/final/factor_research_report.md"),
        exists("src/backtest/execution.py")
        and file_contains_all("reports/final/factor_research_report.md", ("## Strict Execution", "spread", "slippage", "market impact")),
        "Execution utilities exist; final completion requires a data-backed strict-execution section in the final report.",
    )
    add(
        "risk_attribution",
        "Benchmark-relative performance, market regression, industry attribution, and style exposure checks",
        ("src/analysis/attribution.py", "reports/final/factor_research_report.md"),
        exists("src/analysis/attribution.py")
        and file_contains_all(
            "reports/final/factor_research_report.md",
            ("## Benchmark Attribution", "market regression", "industry attribution", "style exposure"),
        ),
        "Attribution code exists; final completion requires a data-backed benchmark/style/industry attribution section.",
    )
    add(
        "robustness",
        "Subperiod, parameter, stock-pool, cost, and walk-forward/sample-out robustness tests",
        ("reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md", "reports/final/factor_research_report.md"),
        exists("reports/eot_factor_drift_feasibility/weekly_eot_drift_robustness_report.md")
        and file_contains_all(
            "reports/final/factor_research_report.md",
            ("## Robustness", "subperiod", "walk-forward", "stock-pool"),
        ),
        "EOT smoothing/cost sensitivity exists; final report adds subperiod, walk-forward, and stock-pool diagnostics.",
    )
    add(
        "engineering",
        "Config, README, tests, modular source tree, and reproducible one-command workflow",
        (
            "config/config.yaml",
            "README.md",
            "tests/test_research_modules.py",
            "scripts/run_full_research_pipeline.py",
            "reports/final/factor_research_report.md",
        ),
        all(
            exists(path)
            for path in (
                "config/config.yaml",
                "README.md",
                "tests/test_research_modules.py",
                "scripts/run_full_research_pipeline.py",
            )
        )
        and file_contains_all("reports/final/factor_research_report.md", ("## Reproducibility", "run_full_research_pipeline.py --full")),
        "A full cached-data one-command entry exists and the final report records reproducibility evidence.",
    )
    return requirements


def write_report(requirements: list[Requirement]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([r.__dict__ for r in requirements])
    df["evidence_paths"] = df["evidence_paths"].apply(lambda paths: "; ".join(paths))
    df.to_csv(REPORT_DIR / "outline_completion_audit.csv", index=False)

    total = len(df)
    complete = int((df["status"] == "complete").sum())
    lines = [
        "# A-Share Multifactor Outline Completion Audit",
        "",
        f"- Completed requirements: {complete}/{total}",
        f"- Incomplete requirements: {total - complete}/{total}",
        "- Completion standard: a requirement is complete only when current files provide direct evidence.",
        "",
        "| section | status | requirement | evidence | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| {row['section']} | {row['status']} | {row['requirement']} | `{row['evidence_paths']}` | {row['notes']} |"
        )
    lines.append("")
    lines.append("## Current Judgment")
    lines.append("")
    if complete == total:
        lines.append("The outline is fully complete according to the current audit evidence.")
    else:
        lines.append(
            "The outline is not fully complete yet. The highest-priority missing pieces are point-in-time "
            "fundamental data, industry/market-cap data, strict execution modeling, attribution, and the final "
            "one-command reproducible pipeline."
        )
    (REPORT_DIR / "outline_completion_audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    requirements = collect_requirements()
    write_report(requirements)
    print(f"Wrote {REPORT_DIR / 'outline_completion_audit.md'}")


if __name__ == "__main__":
    main()
