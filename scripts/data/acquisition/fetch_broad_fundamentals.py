from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.data.akshare_financials import STATEMENT_SPECS, fetch_statement, read_universe


def ticker_to_baostock_code(ticker: str) -> str:
    ticker = str(ticker).zfill(6)
    return f"sh.{ticker}" if ticker.startswith(("5", "6", "9")) else f"sz.{ticker}"

RAW_ROOT = ROOT / "data/raw/coverage_expansion/financial_statements"
INDUSTRY_PATH = ROOT / "data/raw/coverage_expansion/industry_snapshot.parquet"


def fetch_industry(tickers: list[str], force: bool = False) -> pd.DataFrame:
    if INDUSTRY_PATH.exists() and not force:
        return pd.read_parquet(INDUSTRY_PATH)
    try:
        import baostock as bs
    except ImportError as exc:
        logging.warning("BaoStock is unavailable; writing an empty industry snapshot: %s", exc)
        return pd.DataFrame()
    login = bs.login()
    if login.error_code != "0":
        logging.warning("BaoStock login failed: %s", login.error_msg)
        return pd.DataFrame()
    rows = []
    ticker_set = {str(t).zfill(6) for t in tickers}
    try:
        # BaoStock exposes a bulk endpoint when no code is supplied.  It is
        # both more complete and substantially less rate-limit prone than
        # issuing one request per ticker.
        rs = bs.query_stock_industry()
        if rs.error_code != "0":
            logging.warning("bulk industry query failed: %s", rs.error_msg)
        else:
            while rs.next():
                row = dict(zip(rs.fields, rs.get_row_data()))
                code = str(row.get("code", ""))
                ticker = code.split(".")[-1].zfill(6)
                if ticker in ticker_set:
                    row["ticker"] = ticker
                    rows.append(row)
    finally:
        bs.logout()
    out = pd.DataFrame(rows)
    INDUSTRY_PATH.parent.mkdir(parents=True, exist_ok=True); out.to_parquet(INDUSTRY_PATH, index=False)
    return out


def fetch_one_ticker(
    ticker: str,
    start_date: str,
    end_date: str,
    force: bool,
    retries: int,
    sleep_min: float,
    sleep_max: float,
) -> dict[str, object]:
    row: dict[str, object] = {"ticker": ticker}
    for statement_type in STATEMENT_SPECS:
        result = fetch_statement(
            ticker, statement_type, RAW_ROOT, start_date, end_date,
            force, retries, sleep_min, sleep_max,
        )
        row[f"{statement_type}_status"] = result.status
        row[f"{statement_type}_rows"] = result.rows
        row[f"{statement_type}_error"] = result.error
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch broad financial statements and coarse-industry inputs.")
    parser.add_argument("--start-date", default="2014-01-01"); parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--start", type=int, default=0); parser.add_argument("--limit", type=int); parser.add_argument("--force", action="store_true")
    parser.add_argument("--retries", type=int, default=3); parser.add_argument("--sleep-min", type=float, default=0.5); parser.add_argument("--sleep-max", type=float, default=2.0)
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tickers = read_universe(ROOT)[args.start:]; tickers = tickers[:args.limit] if args.limit else tickers
    if not tickers: raise RuntimeError("Selected universe is empty")
    rows = []
    report_dir = ROOT / "reports/coverage_expansion"; report_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_path = report_dir / "fetch_diagnostics.csv"
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fetch_one_ticker, ticker, args.start_date, args.end_date, args.force, args.retries, args.sleep_min, args.sleep_max): ticker
            for ticker in tickers
        }
        for i, future in enumerate(as_completed(futures), start=1):
            ticker = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                rows.append({"ticker": ticker, "error": f"{type(exc).__name__}: {exc}"})
            if i == 1 or i % 10 == 0 or i == len(tickers):
                logging.info("financial completed %s/%s", i, len(tickers))
            pd.DataFrame(rows).sort_values("ticker").to_csv(diagnostics_path, index=False)
    industry = fetch_industry(tickers, args.force); logging.info("industry rows=%s tickers=%s", len(industry), industry["ticker"].nunique() if "ticker" in industry else 0)


if __name__ == "__main__":
    main()
