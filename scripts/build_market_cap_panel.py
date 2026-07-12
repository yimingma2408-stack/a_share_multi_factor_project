from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.akshare_financials import save_frame_with_fallback
from src.data.market_cap_panel import (
    align_to_project_trading_days,
    fetch_market_cap_history,
    find_existing_market_cap_panel,
    read_market_cap_universe,
)


RAW_ROOT = ROOT / "data/raw/akshare/market_cap"
OUTPUT_PATH = ROOT / "data/processed/market_cap_panel.parquet"
AUDIT_PATH = ROOT / "reports/market_cap_data_audit.md"
DIAGNOSTICS_PATH = ROOT / "reports/market_cap_data_diagnostics.csv"


def parse_args() -> argparse.Namespace:
    """Parse market-cap build options."""
    parser = argparse.ArgumentParser(description="Build a point-in-time-safe daily A-share market-cap panel.")
    parser.add_argument("--start-date", default="20160101")
    parser.add_argument("--end-date", default="20251231")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep-min", type=float, default=0.5)
    parser.add_argument("--sleep-max", type=float, default=2.0)
    return parser.parse_args()


def _pct(value: float) -> str:
    return "NA" if pd.isna(value) else f"{100 * value:.2f}%"


def _table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    lines.extend(
        "| " + " | ".join("" if pd.isna(value) else str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def write_audit(
    panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
    metadata: dict[str, object],
    exact_alignment: float,
) -> None:
    """Write source, unit, coverage, anomaly, and failure diagnostics."""
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["market_cap_observation_date"] = pd.to_datetime(
        panel["market_cap_observation_date"], errors="coerce"
    )
    covered = panel.dropna(subset=["market_cap", "date"]).copy()
    annual = (
        covered.assign(year=covered["date"].dt.year)
        .groupby("year")["ticker"]
        .nunique()
        .rename("covered_tickers")
        .reset_index()
        if not covered.empty
        else pd.DataFrame(columns=["year", "covered_tickers"])
    )
    positive = pd.to_numeric(panel["market_cap"], errors="coerce")
    valid = positive[positive > 0]
    anomaly_ratio = float((valid > valid.median() * 1000).mean()) if len(valid) else np.nan
    failures = diagnostics[diagnostics["status"].eq("failed")][["ticker", "error_message"]].head(20)
    sources = panel["market_cap_source"].value_counts(dropna=False).rename_axis("source").reset_index(name="rows")
    fallback_used = bool(panel["market_cap_source"].astype(str).str.contains("fallback").any())
    lines = [
        "# Market-Cap Data Audit",
        "",
        "## Summary",
        "",
        f"- Requested tickers: {len(diagnostics)}.",
        f"- Successful/cached/fallback tickers: {int((diagnostics['status'].astype(str).str.startswith('success') | diagnostics['status'].isin(['cached', 'fallback', 'existing'])).sum())}.",
        f"- Failed tickers: {int(diagnostics['status'].eq('failed').sum())}.",
        f"- Date range: {panel['date'].min()} to {panel['date'].max()}.",
        f"- `market_cap` missing rate: {_pct(panel['market_cap'].isna().mean())}.",
        f"- `float_market_cap` missing rate: {_pct(panel['float_market_cap'].isna().mean())}.",
        f"- Non-positive total-market-cap rows: {int(positive.le(0).sum())}.",
        f"- Extreme rows above 1000x positive median: {_pct(anomaly_ratio)}.",
        f"- Exact alignment with project trading rows before backward as-of: {_pct(exact_alignment)}.",
        f"- Backward as-of future-date violations: {int((panel['market_cap_observation_date'] > panel['date']).sum())}.",
        f"- Fallback source used: {fallback_used}.",
        "",
        "## Source and Unit",
        "",
        _table(sources),
        "",
        f"- Source field: `{metadata.get('source_field', '总市值')}`.",
        f"- Source unit: `{metadata.get('source_unit', '元')}`.",
        f"- Converted unit: `元`.",
        f"- Multiplier: `{metadata.get('multiplier', 1.0)}`.",
        f"- Unit rule: {metadata.get('source_unit_rule', 'AKShare stock_value_em official documentation: yuan')}.",
        "",
        "## Annual Coverage",
        "",
        _table(annual),
        "",
        "## Download Diagnostics",
        "",
        _table(diagnostics.drop(columns=["error_message"], errors="ignore")),
        "",
        "## Failed Tickers (sample)",
        "",
        _table(failures),
        "",
        "## Risk and Next Steps",
        "",
        "- Total and float market cap are taken directly from daily market data; turnover/amount are never substituted.",
        "- Missing source dates are filled only with the most recent past observation using backward as-of.",
        "- The Baidu fallback, if present, is explicitly labelled and uses an inferred 1e8 multiplier; production use should prefer Eastmoney.",
        "- Retry failed tickers incrementally. Cached successful files are skipped unless `--force` is supplied.",
    ]
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Build the unified panel from existing data or historical AKShare valuation data."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start_date = pd.Timestamp(args.start_date)
    end_date = pd.Timestamp(args.end_date)
    tickers = read_market_cap_universe(ROOT)[args.start :]
    if args.limit is not None:
        tickers = tickers[: args.limit]
    if not tickers:
        raise RuntimeError("The selected universe slice is empty")
    existing = find_existing_market_cap_panel(ROOT, start_date, end_date)
    diagnostics_rows = []
    metadata: dict[str, object]
    if existing is not None:
        source, metadata = existing
        source = source[source["ticker"].isin(tickers)]
        for ticker in tickers:
            rows = source[source["ticker"].eq(ticker)]
            diagnostics_rows.append(
                {
                    "ticker": ticker,
                    "status": "existing" if len(rows) else "failed",
                    "n_rows": len(rows),
                    "first_date": rows["date"].min() if len(rows) else pd.NaT,
                    "last_date": rows["date"].max() if len(rows) else pd.NaT,
                    "market_cap_missing_rate": rows["market_cap"].isna().mean() if len(rows) else 1.0,
                    "float_market_cap_missing_rate": rows["float_market_cap"].isna().mean() if len(rows) else 1.0,
                    "source": rows["market_cap_source"].iloc[0] if len(rows) else "",
                    "error_message": "" if len(rows) else "ticker absent from existing market-cap source",
                }
            )
    else:
        frames = []
        metadata = {
            "source_field": "总市值 / 流通市值",
            "source_unit": "元",
            "multiplier": 1.0,
            "source_unit_rule": "AKShare stock_value_em official documentation: yuan",
        }
        for position, ticker in enumerate(tickers, start=1):
            logging.info("[%s/%s] market cap %s", position, len(tickers), ticker)
            result = fetch_market_cap_history(
                ticker,
                RAW_ROOT,
                start_date,
                end_date,
                force=args.force,
                retries=args.retries,
                sleep_min=args.sleep_min,
                sleep_max=args.sleep_max,
            )
            rows = result.frame
            if not rows.empty:
                frames.append(rows)
            diagnostics_rows.append(
                {
                    "ticker": ticker,
                    "status": result.status,
                    "n_rows": len(rows),
                    "first_date": rows["date"].min() if len(rows) else pd.NaT,
                    "last_date": rows["date"].max() if len(rows) else pd.NaT,
                    "market_cap_missing_rate": rows["market_cap"].isna().mean() if len(rows) else 1.0,
                    "float_market_cap_missing_rate": rows["float_market_cap"].isna().mean() if len(rows) else 1.0,
                    "source": result.source,
                    "error_message": result.error_message,
                }
            )
        source = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["date", "ticker", "market_cap", "float_market_cap", "market_cap_source"]
        )
    diagnostics = pd.DataFrame(diagnostics_rows)
    DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False)
    if source.empty:
        empty = source.copy()
        empty["market_cap_observation_date"] = pd.NaT
        save_frame_with_fallback(empty, OUTPUT_PATH)
        write_audit(empty, diagnostics, metadata, np.nan)
        raise RuntimeError("No market-cap rows were available; see reports/market_cap_data_audit.md")
    panel, exact_alignment = align_to_project_trading_days(source, ROOT, tickers, start_date, end_date)
    actual = save_frame_with_fallback(panel, OUTPUT_PATH)
    write_audit(panel, diagnostics, metadata, exact_alignment)
    logging.info("Wrote %s (%s rows, %s tickers)", actual, len(panel), panel["ticker"].nunique())
    logging.info("Wrote %s and %s", AUDIT_PATH, DIAGNOSTICS_PATH)


if __name__ == "__main__":
    main()
