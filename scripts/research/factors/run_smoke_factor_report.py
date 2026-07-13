from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.grouping import quantile_group_returns
from src.analysis.ic import compute_rank_ic, summarize_ic
from src.analysis.decay import add_forward_returns, compute_ic_decay
from src.factors.preprocess import preprocess_by_date
from src.factors.price_volume import build_price_volume_factor_panel

INPUT = ROOT / "data/processed/clean_daily_data.csv"
REPORT_DIR = ROOT / "reports/completion_audit"


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "No rows generated."
    display = df.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{x:.6g}")
        else:
            display[col] = display[col].astype(str)
    header = "| " + " | ".join(display.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in display.to_numpy(dtype=str)]
    return "\n".join([header, sep, *rows])


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    daily = pd.read_csv(INPUT)
    daily["date"] = pd.to_datetime(daily["date"])
    panel = build_price_volume_factor_panel(daily, price_col="close")
    panel = add_forward_returns(panel, horizons=(1, 5, 10, 20, 60), price_col="close")

    month_ends = panel.groupby(panel["date"].dt.to_period("M"))["date"].max().sort_values()
    monthly = panel[panel["date"].isin(month_ends.values)].sort_values(["ticker", "date"]).copy()
    monthly["next_close"] = monthly.groupby("ticker")["close"].shift(-1)
    monthly["fwd_ret_1m"] = monthly["next_close"] / monthly["close"] - 1.0

    factor_cols = ["mom_60_20d", "reversal_20d", "lowvol_20d", "lowturn_20d", "liquidity_20d"]
    available = [col for col in factor_cols if col in monthly.columns]
    monthly = preprocess_by_date(monthly, available)
    zcols = [f"{col}_z" for col in available]

    ic = compute_rank_ic(monthly, zcols, "fwd_ret_1m", min_obs=30)
    ic_summary = summarize_ic(ic)
    daily_decay = preprocess_by_date(panel, available)
    decay_summary = compute_ic_decay(daily_decay, zcols, horizons=(1, 5, 10, 20, 60), min_obs=30)
    grouped = pd.concat(
        [quantile_group_returns(monthly, col, "fwd_ret_1m", groups=5, min_obs=30) for col in zcols],
        ignore_index=True,
    )
    group_summary = (
        grouped.groupby("factor_name")["long_short_return"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(columns={"mean": "mean_long_short_return", "std": "std_long_short_return", "count": "observations"})
    )

    ic.to_csv(REPORT_DIR / "smoke_rank_ic.csv", index=False)
    ic_summary.to_csv(REPORT_DIR / "smoke_rank_ic_summary.csv", index=False)
    decay_summary.to_csv(REPORT_DIR / "smoke_ic_decay_summary.csv", index=False)
    group_summary.to_csv(REPORT_DIR / "smoke_group_summary.csv", index=False)

    lines = [
        "# Smoke Factor Report",
        "",
        "This lightweight report uses `data/processed/clean_daily_data.csv` and the reusable modules under `src/`.",
        "It is a local reproducibility smoke test, not the final full-universe research report.",
        "",
        f"- Daily rows: {len(daily)}",
        f"- Tickers: {daily['ticker'].nunique()}",
        f"- Date range: {daily['date'].min().date()} to {daily['date'].max().date()}",
        f"- Monthly rows after factor construction: {len(monthly)}",
        "",
        "## Rank IC Summary",
        "",
        to_markdown_table(ic_summary),
        "",
        "## Daily IC Decay Summary",
        "",
        to_markdown_table(decay_summary),
        "",
        "## Grouped Long-Short Summary",
        "",
        to_markdown_table(group_summary),
        "",
        "## Remaining Gap",
        "",
        "This smoke test covers price/volume factors only. Value factors, neutralized factors, attribution, and strict execution still need the missing fundamental, industry, market-cap, benchmark, and execution data.",
    ]
    (REPORT_DIR / "smoke_factor_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_DIR / 'smoke_factor_report.md'}")


if __name__ == "__main__":
    main()
