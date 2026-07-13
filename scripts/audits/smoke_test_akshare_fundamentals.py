from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
PANEL_PATH = ROOT / "data/processed/fundamental_panel_akshare.parquet"
REPORT_PATH = ROOT / "reports/akshare_fundamental_smoke_test.md"
CORE_COLUMNS = [
    "date",
    "ticker",
    "report_date",
    "available_date",
    "revenue_ttm",
    "operating_cost_ttm",
    "gross_profit_ttm",
    "net_profit_ttm",
    "net_profit_parent_ttm",
    "operating_cash_flow_ttm",
    "total_assets",
    "total_equity",
    "equity_parent",
    "market_cap",
]
FACTOR_COLUMNS = [
    "bp",
    "ep",
    "sp",
    "cfp",
    "roe",
    "gross_profitability",
    "ocf_to_assets",
    "revenue_growth",
    "earnings_growth",
]


def main() -> None:
    """Validate required columns, PIT ordering, and non-empty factor values."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    path = PANEL_PATH if PANEL_PATH.exists() else PANEL_PATH.with_suffix(".csv")
    if not path.exists():
        raise FileNotFoundError(f"Fundamental panel is missing: {PANEL_PATH} (or CSV fallback)")
    panel = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["available_date"] = pd.to_datetime(panel["available_date"], errors="coerce")
    missing_columns = [col for col in CORE_COLUMNS + FACTOR_COLUMNS if col not in panel]
    pit_violations = int((panel["available_date"] > panel["date"]).sum()) if not missing_columns else -1
    factor_counts = {col: int(panel[col].notna().sum()) if col in panel else 0 for col in FACTOR_COLUMNS}
    checks = {
        "panel_exists": True,
        "core_columns_present": not missing_columns,
        "point_in_time_valid": pit_violations == 0,
        "all_factors_have_values": all(count > 0 for count in factor_counts.values()),
    }
    lines = [
        "# AKShare Fundamental Smoke Test",
        "",
        f"- Panel: `{path.relative_to(ROOT)}`",
        f"- Rows: {len(panel)}",
        f"- Tickers: {panel['ticker'].nunique() if 'ticker' in panel else 0}",
        f"- Missing required columns: {missing_columns or 'none'}",
        f"- Point-in-time violations: {pit_violations}",
        "",
        "## Factor Non-Missing Counts",
        "",
        "| factor | non-missing rows |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {factor} | {count} |" for factor, count in factor_counts.items())
    lines.extend(
        [
            "",
            "## Result",
            "",
            "| check | passed |",
            "| --- | --- |",
        ]
    )
    lines.extend(f"| {name} | {passed} |" for name, passed in checks.items())
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    logging.info("Wrote %s", REPORT_PATH)
    if not all(checks.values()):
        raise SystemExit("Smoke test failed; see reports/akshare_fundamental_smoke_test.md")


if __name__ == "__main__":
    main()
