from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.akshare_financials import STATEMENT_SPECS, fetch_statement, read_universe


RAW_ROOT = ROOT / "data/raw/akshare/financial_statements"
DIAGNOSTICS_PATH = ROOT / "reports/akshare_financial_data_diagnostics.csv"


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Fetch cached A-share financial statements from AKShare.")
    parser.add_argument("--start-date", default="20140101")
    parser.add_argument("--end-date", default="20251231")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep-min", type=float, default=0.5)
    parser.add_argument("--sleep-max", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    """Download all three statements with caching, retries, and diagnostics."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.sleep_min < 0 or args.sleep_max < args.sleep_min:
        raise ValueError("Require 0 <= --sleep-min <= --sleep-max")
    tickers = read_universe(ROOT)[args.start :]
    if args.limit is not None:
        tickers = tickers[: args.limit]
    if not tickers:
        raise RuntimeError("The selected universe slice is empty")

    rows = []
    for position, ticker in enumerate(tickers, start=1):
        logging.info("[%s/%s] downloading %s", position, len(tickers), ticker)
        row: dict[str, object] = {"ticker": ticker, "error_message": ""}
        errors = []
        for statement_type in STATEMENT_SPECS:
            result = fetch_statement(
                ticker,
                statement_type,
                RAW_ROOT,
                start_date=pd.Timestamp(args.start_date),
                end_date=pd.Timestamp(args.end_date),
                force=args.force,
                retries=args.retries,
                sleep_min=args.sleep_min,
                sleep_max=args.sleep_max,
            )
            prefix = {
                "balance_sheet": "balance",
                "profit_sheet": "profit",
                "cash_flow_sheet": "cashflow",
            }[statement_type]
            row[f"{statement_type}_status"] = result.status
            row[f"{statement_type}_source"] = result.source
            row[f"n_{prefix}_rows"] = result.rows
            if result.error:
                errors.append(f"{statement_type}: {result.error}")
        row["error_message"] = " | ".join(errors)
        rows.append(row)

    diagnostics = pd.DataFrame(rows)
    DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False)
    successes = diagnostics[[f"{name}_status" for name in STATEMENT_SPECS]].isin(["success", "cached"])
    logging.info("Downloaded/cached %s tickers; all-three success: %s", len(diagnostics), int(successes.all(axis=1).sum()))
    logging.info("Diagnostics: %s", DIAGNOSTICS_PATH)


if __name__ == "__main__":
    main()
