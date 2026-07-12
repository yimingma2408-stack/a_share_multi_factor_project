from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.pit_audit import audit_point_in_time_coverage


PANELS = {
    "five_ticker_akshare": ROOT / "data/processed/fundamental_panel_akshare_with_market_cap.parquet",
    "broad_coverage_expansion": ROOT / "data/processed/coverage_expansion/fundamental_panel_broad.parquet",
}
REPORT = ROOT / "reports/data_quality"


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, path in PANELS.items():
        if not path.exists():
            rows.append({"panel_name": name, "path": str(path), "status": "missing"})
            continue
        result = audit_point_in_time_coverage(pd.read_parquet(path), name).as_dict()
        result.update({"path": str(path), "status": "available"})
        rows.append(result)
    output = pd.DataFrame(rows)
    output.to_csv(REPORT / "point_in_time_coverage_audit.csv", index=False)
    lines = ["# Point-in-Time and Coverage Audit", ""]
    for row in rows:
        lines.extend([
            f"## {row['panel_name']}", "",
            f"- Status: `{row['status']}`",
            f"- Source: `{row['path']}`",
        ])
        if row["status"] == "available":
            lines.extend([
                f"- Rows / tickers / dates: {row['rows']:,} / {row['tickers']} / {row['dates']}",
                f"- Date range: {row['start_date']} to {row['end_date']}",
                f"- Available-date coverage: {row['available_date_coverage']:.2%}",
                f"- Future-date violations: {row['future_available_date_violations']}",
                f"- PIT-safe industry ratio: {row['industry_pit_safe_ratio']:.2%}",
                f"- Float/market-cap coverage: {row['float_cap_coverage']:.2%}",
                f"- Formal multifactor eligibility: {'YES' if row['usable_for_formal_multifactor'] else 'NO'}",
                f"- Exclusion reason: {row['formal_exclusion_reason'] or 'None'}",
            ])
        lines.append("")
    lines.extend([
        "## Decision",
        "",
        "Neither panel is automatically promoted into the headline formal lifecycle/backtest universe by this audit. "
        "The five-ticker panel lacks cross-sectional breadth; the broad panel has no dated PIT-safe industry history. "
        "Both remain documented research inputs until the failed eligibility condition is resolved.",
    ])
    (REPORT / "point_in_time_coverage_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(output[["panel_name", "status", "usable_for_formal_multifactor", "formal_exclusion_reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
