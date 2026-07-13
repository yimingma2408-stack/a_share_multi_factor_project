from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
FUNDAMENTAL_PATH = ROOT / "data/processed/fundamental_panel_akshare.parquet"
MARKET_CAP_PATH = ROOT / "data/processed/market_cap_panel.parquet"
REPORT_PATH = ROOT / "reports/market_cap_factor_smoke_test.md"
FACTORS = [
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


def _distribution(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor in FACTORS:
        values = pd.to_numeric(panel[factor], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        rows.append(
            {
                "factor": factor,
                "non_missing_rate": values.size / len(panel) if len(panel) else 0.0,
                "mean": values.mean(),
                "std": values.std(),
                "min": values.min(),
                "p1": values.quantile(0.01),
                "p50": values.median(),
                "p99": values.quantile(0.99),
                "max": values.max(),
            }
        )
    return pd.DataFrame(rows)


def _table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    lines.extend(
        "| " + " | ".join("" if pd.isna(value) else f"{value:.6g}" if isinstance(value, float) else str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def main() -> None:
    """Check market-cap coverage, factor distributions, anomalies, and PIT safety."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not FUNDAMENTAL_PATH.exists() or not MARKET_CAP_PATH.exists():
        missing = [str(path) for path in [FUNDAMENTAL_PATH, MARKET_CAP_PATH] if not path.exists()]
        raise FileNotFoundError(f"Required panels are missing: {missing}")
    panel = pd.read_parquet(FUNDAMENTAL_PATH)
    market_caps = pd.read_parquet(MARKET_CAP_PATH)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["available_date"] = pd.to_datetime(panel["available_date"], errors="coerce")
    panel["market_cap_observation_date"] = pd.to_datetime(panel["market_cap_observation_date"], errors="coerce")
    distribution = _distribution(panel)
    rates = distribution.set_index("factor")["non_missing_rate"]
    market_rate = float(panel["market_cap"].notna().mean())
    financial_violations = int((panel["available_date"] > panel["date"]).sum())
    cap_violations = int((panel["market_cap_observation_date"] > panel["date"]).sum())
    non_positive = int(pd.to_numeric(panel["market_cap"], errors="coerce").le(0).sum())
    ep = pd.to_numeric(panel["ep"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    extreme_ep = int(ep.abs().gt(10).sum())
    checks = {
        "fundamental_panel_exists": FUNDAMENTAL_PATH.exists(),
        "market_cap_panel_exists": MARKET_CAP_PATH.exists(),
        "market_cap_non_missing_gt_90pct": market_rate > 0.90,
        "bp_non_missing_gt_70pct": rates["bp"] > 0.70,
        "ep_non_missing_gt_70pct": rates["ep"] > 0.70,
        "sp_non_missing_gt_70pct": rates["sp"] > 0.70,
        "cfp_non_missing_gt_70pct": rates["cfp"] > 0.70,
        "value_composite_non_missing_gt_70pct": rates["value_composite_raw"] > 0.70,
        "quality_growth_factors_remain_available": all(rates[name] > 0 for name in FACTORS[5:]),
        "point_in_time_violations_zero": financial_violations == 0 and cap_violations == 0,
        "market_cap_positive": non_positive == 0,
        "no_abs_ep_above_10": extreme_ep == 0,
    }
    check_frame = pd.DataFrame({"check": checks.keys(), "passed": checks.values()})
    lines = [
        "# Market-Cap Factor Smoke Test",
        "",
        f"- Fundamental rows/tickers: {len(panel)} / {panel['ticker'].nunique()}.",
        f"- Market-cap panel rows/tickers: {len(market_caps)} / {market_caps['ticker'].nunique()}.",
        f"- Market-cap non-missing rate: {market_rate:.2%}.",
        f"- Financial PIT violations: {financial_violations}.",
        f"- Market-cap PIT violations: {cap_violations}.",
        f"- Non-positive market caps: {non_positive}.",
        f"- Rows with `abs(ep) > 10`: {extreme_ep}.",
        "",
        "## Factor Distribution",
        "",
        _table(distribution),
        "",
        "## Checks",
        "",
        _table(check_frame),
        "",
        f"## Final Result: {'PASS' if all(checks.values()) else 'FAIL'}",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    logging.info("Wrote %s", REPORT_PATH)
    if not all(checks.values()):
        raise SystemExit("Market-cap factor smoke test failed; see reports/market_cap_factor_smoke_test.md")


if __name__ == "__main__":
    main()
