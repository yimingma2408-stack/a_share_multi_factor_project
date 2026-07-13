from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.data.coverage_expansion import load_broad_statements, build_broad_monthly_panel

RAW_ROOT = ROOT / "data/raw/coverage_expansion/financial_statements"
INDUSTRY_PATH = ROOT / "data/raw/coverage_expansion/industry_snapshot.parquet"
PANEL_PATH = ROOT / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"
CAP_PATH = ROOT / "data/processed/market_cap_panel.parquet"
OUT_DIR = ROOT / "data/processed/coverage_expansion"
REPORT_DIR = ROOT / "reports/coverage_expansion"


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--start-date", default="2014-01-01"); parser.add_argument("--end-date", default="2025-12-31")
    args = parser.parse_args(); OUT_DIR.mkdir(parents=True, exist_ok=True); REPORT_DIR.mkdir(parents=True, exist_ok=True)
    statements, mappings = load_broad_statements(RAW_ROOT, args.start_date, args.end_date)
    dynamic = pd.read_parquet(PANEL_PATH); caps = pd.read_parquet(CAP_PATH); industry = pd.read_parquet(INDUSTRY_PATH) if INDUSTRY_PATH.exists() else pd.DataFrame()
    panel = build_broad_monthly_panel(statements, dynamic, caps, industry)
    panel.to_parquet(OUT_DIR / "fundamental_panel_broad.parquet", index=False); mappings.to_csv(REPORT_DIR / "field_mapping.csv", index=False)
    print(f"Wrote broad fundamental panel: rows={len(panel)} tickers={panel['ticker'].nunique()}")


if __name__ == "__main__":
    main()
