from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.akshare_financials import (
    STATEMENT_SPECS,
    add_ttm_and_growth,
    build_point_in_time_panel,
    load_statement_directory,
    merge_statements,
    save_frame_with_fallback,
)


RAW_ROOT = ROOT / "data/raw/akshare/financial_statements"
OUTPUT_PATH = ROOT / "data/processed/fundamental_panel_akshare.parquet"
STATEMENT_PATH = ROOT / "data/processed/fundamental_statements_akshare.parquet"
AUDIT_PATH = ROOT / "reports/akshare_financial_data_audit.md"
DIAGNOSTICS_PATH = ROOT / "reports/akshare_financial_data_diagnostics.csv"

FACTOR_COLUMNS = [
    "bp",
    "ep",
    "sp",
    "cfp",
    "value_composite_raw",
    "roe",
    "gross_profitability",
    "ocf_to_assets",
    "revenue_growth",
    "earnings_growth",
]


def parse_args() -> argparse.Namespace:
    """Parse build options."""
    parser = argparse.ArgumentParser(description="Build a point-in-time fundamental panel from cached AKShare statements.")
    parser.add_argument("--start-date", default="2014-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    return parser.parse_args()


def _pct(value: float) -> str:
    return f"{100 * value:.2f}%"


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join("" if pd.isna(value) else str(value) for value in row) + " |")
    return "\n".join(lines)


def write_audit(
    statements: dict[str, pd.DataFrame],
    mappings: pd.DataFrame,
    panel: pd.DataFrame,
    market_cap_source: str,
    output_path: Path,
) -> None:
    """Write the human-readable data provenance and quality audit."""
    diagnostics = pd.read_csv(DIAGNOSTICS_PATH) if DIAGNOSTICS_PATH.exists() else pd.DataFrame()
    status_rows = []
    for statement_type in STATEMENT_SPECS:
        status_col = f"{statement_type}_status"
        if status_col in diagnostics:
            good = diagnostics[status_col].isin(["success", "cached"])
            success = int(good.sum())
            total = len(diagnostics)
        else:
            frame = statements.get(statement_type, pd.DataFrame())
            success = int(frame["ticker"].nunique()) if not frame.empty else 0
            total = success
        status_rows.append(
            {
                "statement": statement_type,
                "successful_tickers": success,
                "requested_tickers": total,
                "success_rate": _pct(success / total) if total else "NA",
            }
        )
    status = pd.DataFrame(status_rows)

    mapping_summary = (
        mappings[mappings["target_field"].ne("__file_error__")]
        .groupby(["statement_type", "target_field"])["source_column"]
        .agg(lambda values: ", ".join(sorted({str(v) for v in values.dropna()})) or "MISSING")
        .reset_index()
        if not mappings.empty
        else pd.DataFrame()
    )
    schema_rows = []
    for statement_type in STATEMENT_SPECS:
        schema_files = sorted((RAW_ROOT / statement_type).glob(f"*_{statement_type}_columns.json"))
        field_names: set[str] = set()
        for schema_file in schema_files:
            try:
                field_names.update(json.loads(schema_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        schema_rows.append(
            {
                "statement": statement_type,
                "schema_files": len(schema_files),
                "unique_columns": len(field_names),
                "field_summary": ", ".join(sorted(field_names)[:30]) + (" ..." if len(field_names) > 30 else ""),
            }
        )
    schema_summary = pd.DataFrame(schema_rows)
    core_fields = [
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
    missing = pd.DataFrame(
        {
            "field": core_fields,
            "missing_rate": [_pct(panel[col].isna().mean()) for col in core_fields],
        }
    )
    factor_coverage = pd.DataFrame(
        {
            "factor": FACTOR_COLUMNS,
            "non_missing_rate": [_pct(panel[col].notna().mean()) for col in FACTOR_COLUMNS],
        }
    )
    annual = (
        panel.assign(year=panel["date"].dt.year)
        .groupby("year")
        .agg(
            covered_tickers=("ticker", lambda values: panel.loc[values.index, "report_date"].notna().groupby(values).any().sum()),
            panel_rows=("ticker", "size"),
        )
        .reset_index()
    )
    date_methods = (
        panel["available_date_method"].value_counts(dropna=False).rename_axis("method").reset_index(name="rows")
    )
    failures = (
        diagnostics[diagnostics.get("error_message", pd.Series(index=diagnostics.index, dtype=str)).fillna("").ne("")]
        [["ticker", "error_message"]]
        .head(20)
        if not diagnostics.empty and "error_message" in diagnostics
        else pd.DataFrame()
    )
    raw_formats = sorted({path.suffix for path in RAW_ROOT.rglob("*") if path.suffix in {".parquet", ".csv"}})
    actual_output = output_path if output_path.exists() else output_path.with_suffix(".csv")
    pit_violations = int((panel["available_date"] > panel["date"]).sum())
    lines = [
        "# AKShare Financial Data Audit",
        "",
        "## Summary",
        "",
        f"- Requested/download diagnostic tickers: {len(diagnostics)}.",
        f"- Tickers represented in the final panel: {panel['ticker'].nunique()}.",
        f"- Final panel rows: {len(panel)}.",
        f"- Final output: `{actual_output.relative_to(ROOT)}`.",
        f"- Raw formats present: {', '.join(raw_formats) if raw_formats else 'none'}.",
        f"- Market-cap source: `{market_cap_source}`.",
        f"- Point-in-time violations (`available_date > date`): {pit_violations}.",
        "",
        "## Statement Download Success",
        "",
        _markdown_table(status),
        "",
        "## Target Field Mapping",
        "",
        _markdown_table(mapping_summary),
        "",
        "## Raw Field Lists",
        "",
        _markdown_table(schema_summary),
        "",
        "## Core Field Missing Rates",
        "",
        _markdown_table(missing),
        "",
        "## Annual Stock Coverage",
        "",
        _markdown_table(annual),
        "",
        "## Factor Non-Missing Rates",
        "",
        _markdown_table(factor_coverage),
        "",
        "## Available-Date Provenance",
        "",
        _markdown_table(date_methods),
        "",
        "- `reported`: AKShare supplied an announcement/update/disclosure date for every contributing statement.",
        "- `conservative_lag`: no real availability date was supplied; quarter-specific 45/75/45/120-day lags were used.",
        "- `mixed`: at least one contributing statement used each method. The merged availability date is the latest contributing date.",
        "",
        "## Point-in-Time Assessment",
        "",
        "The trade-date panel is built with a backward as-of merge and therefore only uses rows where "
        "`available_date <= date`. Financial flows are treated as cumulative year-to-date values, converted "
        "to single quarters, and only then rolled over four consecutive quarters. Missing quarters are not filled.",
        "",
        "Residual risk remains because provider snapshots may contain later restatements without revision history. "
        "The code never substitutes report date for availability date, but a snapshot API cannot reconstruct "
        "every historical version of a restated statement.",
        "",
        "## Failed Tickers (sample)",
        "",
        _markdown_table(failures),
        "",
        "## Next Steps",
        "",
        "- Retry failed tickers incrementally; cached files are skipped by default.",
        "- Supply a genuine point-in-time market-cap panel. Price multiplied by statement share capital is deliberately not used.",
        "- For production, archive dated provider snapshots or obtain revision-aware fundamentals to reduce restatement risk.",
    ]
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Build normalized statements, TTM fields, PIT daily panel, and audit."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    statements = {}
    mapping_rows = []
    for statement_type in STATEMENT_SPECS:
        frame, mappings = load_statement_directory(RAW_ROOT, statement_type, args.start_date, args.end_date)
        statements[statement_type] = frame
        mapping_rows.extend(mappings)
        logging.info("%s: %s rows, %s tickers", statement_type, len(frame), frame["ticker"].nunique() if not frame.empty else 0)
    mappings = pd.DataFrame(mapping_rows)
    merged = add_ttm_and_growth(merge_statements(statements))
    save_frame_with_fallback(merged, STATEMENT_PATH)
    panel, market_cap_source = build_point_in_time_panel(merged, ROOT)
    actual_output = save_frame_with_fallback(panel, OUTPUT_PATH)
    write_audit(statements, mappings, panel, market_cap_source, actual_output)
    logging.info("Wrote %s (%s rows, %s tickers)", actual_output, len(panel), panel["ticker"].nunique())
    logging.info("Wrote %s", AUDIT_PATH)


if __name__ == "__main__":
    main()
