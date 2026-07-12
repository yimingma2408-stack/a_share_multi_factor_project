from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.eot_drift import compute_eot_drift
from src.data.coverage_expansion import FACTOR_COLUMNS

OUT = ROOT / "data/processed/coverage_expansion"; REPORT = ROOT / "reports/coverage_expansion"
PANEL = OUT / "fundamental_panel_broad.parquet"; DAILY = ROOT / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"


def _mode_mask(frame: pd.DataFrame, mode: str) -> pd.Series:
    if mode == "strict":
        return frame["available_date"].le(frame["date"]) & frame["industry_pit_safe"].fillna(False) & frame["market_cap_quality_grade"].isin(["A", "B"])
    if mode == "expanded":
        return frame["available_date"].le(frame["date"]) & frame["market_cap_quality_grade"].isin(["A", "B", "C"])
    if mode == "proxy_sensitivity":
        return frame["available_date"].le(frame["date"]) & frame["market_cap_quality_grade"].eq("C")
    raise ValueError(mode)


def _monthly_returns() -> pd.DataFrame:
    daily = pd.read_parquet(DAILY, columns=["date", "ticker", "qfq_close", "is_hs300_member", "trade_status", "is_st"])
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").astype("datetime64[ns]"); daily["ticker"] = daily["ticker"].astype(str).str.zfill(6)
    dates = daily.groupby(daily["date"].dt.to_period("M"))["date"].max()
    m = daily[daily["date"].isin(dates.values)].sort_values(["ticker", "date"])
    m["fwd_ret_1m"] = m.groupby("ticker")["qfq_close"].shift(-1) / m["qfq_close"] - 1
    return m[["date", "ticker", "fwd_ret_1m", "is_hs300_member", "trade_status", "is_st"]]


def _performance(frame: pd.DataFrame, mode: str, returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = frame[_mode_mask(frame, mode)].merge(returns, on=["date", "ticker"], how="left")
    active = returns.groupby("date")["ticker"].nunique().rename("active_universe_count")
    rows, quality = [], []
    for date, group in work.groupby("date", sort=True):
        universe = active.get(date, 0)
        for factor in FACTOR_COLUMNS:
            valid = group[[factor, "fwd_ret_1m", "ticker"]].replace([np.inf, -np.inf], np.nan).dropna()
            ic = valid[factor].corr(valid["fwd_ret_1m"], method="spearman") if len(valid) >= 30 else np.nan
            quality.append({"date": date, "factor_name": factor, "mode": mode, "active_universe_count": universe, "available_stock_count": len(valid), "coverage_ratio": len(valid) / universe if universe else 0.0, "industry_coverage_ratio": group["industry_coarse"].notna().mean(), "financial_field_coverage": group[factor].notna().mean(), "proxy_ratio": group["float_market_cap_is_proxy"].mean(), "level_a_ratio": (group["market_cap_quality_grade"] == "A").mean(), "level_b_ratio": (group["market_cap_quality_grade"] == "B").mean(), "level_c_ratio": (group["market_cap_quality_grade"] == "C").mean(), "quality_grade": "eligible" if len(valid) / universe >= .70 and (group["market_cap_quality_grade"] == "C").mean() <= .20 else ("watch_only" if len(valid) / universe >= .50 else "rejected")})
            if len(valid) < 30: continue
            q = max(int(len(valid) * .2), 1); top = valid.nlargest(q, factor); bottom = valid.nsmallest(q, factor)
            rows.append({"date": date, "factor_name": factor, "mode": mode, "rank_ic": ic, "long_short_return": top["fwd_ret_1m"].mean() - bottom["fwd_ret_1m"].mean(), "n_stocks": len(valid), "coverage_ratio": len(valid) / universe if universe else 0.0})
    return pd.DataFrame(rows), pd.DataFrame(quality)


def _eot_summary(perf: pd.DataFrame) -> float:
    values = []
    for _, group in perf.groupby("factor_name"):
        g = group.sort_values("date")
        for i in range(42, len(g)):
            base = g.iloc[i - 42:i - 6][["rank_ic", "long_short_return"]].dropna().to_numpy()
            recent = g.iloc[i - 6:i][["rank_ic", "long_short_return"]].dropna().to_numpy()
            if len(base) >= 12 and len(recent) >= 3:
                values.append(compute_eot_drift(base, recent, n_reference=50, random_state=42).drift)
    return float(np.nanmean(values)) if values else np.nan


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(PANEL); panel["date"] = pd.to_datetime(panel["date"], errors="coerce").astype("datetime64[ns]"); returns = _monthly_returns()
    all_perf, all_quality, comparisons = [], [], []
    for mode in ["strict", "expanded", "proxy_sensitivity"]:
        perf, quality = _performance(panel, mode, returns); all_perf.append(perf); all_quality.append(quality)
        # Strict mode can legitimately have no eligible rows when a
        # point-in-time-safe industry history is unavailable.  Preserve that
        # diagnostic instead of failing the whole audit.
        if perf.empty:
            continue
        for factor, g in perf.groupby("factor_name"):
            ic_std = g["rank_ic"].std(ddof=1); ls_std = g["long_short_return"].std(ddof=1)
            comparisons.append({"mode": mode, "factor_name": factor, "mean_rank_ic": g["rank_ic"].mean(), "icir": g["rank_ic"].mean() / ic_std if ic_std else np.nan, "mean_long_short_return": g["long_short_return"].mean(), "long_short_t_stat": g["long_short_return"].mean() / (ls_std / math.sqrt(len(g))) if ls_std and len(g) else np.nan, "mean_coverage_ratio": g["coverage_ratio"].mean(), "mean_eot_drift": _eot_summary(g)})
    quality_panel = pd.concat(all_quality, ignore_index=True); quality_panel.to_parquet(OUT / "coverage_quality_panel.parquet", index=False)
    mode_row_counts = {mode: int(len(perf)) for mode, perf in zip(["strict", "expanded", "proxy_sensitivity"], all_perf)}
    comparison = pd.DataFrame(comparisons); comparison.to_csv(REPORT / "strict_vs_expanded_comparison.csv", index=False)
    financial = panel.groupby("ticker", as_index=False).agg(rows=("date", "size"), available_date_coverage=("available_date", lambda s: s.notna().mean()), report_date_coverage=("report_date", lambda s: s.notna().mean()))
    financial.to_csv(REPORT / "financial_coverage_summary.csv", index=False)
    panel.groupby(["industry_coarse"], as_index=False).agg(tickers=("ticker", "nunique"), rows=("ticker", "size"), pit_safe_ratio=("industry_pit_safe", "mean")).to_csv(REPORT / "industry_coverage_summary.csv", index=False)
    panel.groupby("market_cap_quality_grade", as_index=False).agg(rows=("ticker", "size"), tickers=("ticker", "nunique"), proxy_ratio=("float_market_cap_is_proxy", "mean"), coverage=("float_market_cap_used", lambda s: s.notna().mean())).to_csv(REPORT / "market_cap_proxy_summary.csv", index=False)
    pit = int((panel["available_date"] > panel["date"]).sum()); tickers = panel["ticker"].nunique(); target = int(panel["date"].nunique())
    lines = ["# Coverage Expansion Audit", "", f"- Broad panel rows/tickers: {len(panel):,} / {tickers}.", f"- Monthly dates: {target}.", f"- PIT violations (`available_date > date`): {pit}.", f"- Coarse industry buckets: {panel['industry_coarse'].nunique()}.", f"- Industry label coverage: {panel['industry_coarse'].notna().mean():.2%}.", f"- Industry PIT-safe ratio: {panel['industry_pit_safe'].mean():.2%}.", f"- Float-cap used coverage: {panel['float_market_cap_used'].notna().mean():.2%}.", "", "## Mode interpretation", "", "- `strict`: reported/available financial dates, PIT-safe industry, Level A/B cap only.", "- `expanded`: conservative financial lag, latest coarse industry snapshot, Level A/B/C cap.", "- `proxy_sensitivity`: Level C cap rows only; diagnostic, not headline allocation.", "", f"- Eligible performance rows by mode: strict={mode_row_counts['strict']}, expanded={mode_row_counts['expanded']}, proxy_sensitivity={mode_row_counts['proxy_sensitivity']}.", "- Strict has no eligible rows because the available industry data is a latest snapshot (`industry_pit_safe=false`), not a dated historical industry panel.", "", "## Acceptance checks", "", f"- Broad ticker target (500): {'PASS' if tickers >= 500 else 'FAIL'}.", f"- PIT violations zero: {'PASS' if pit == 0 else 'FAIL'}.", f"- Float-cap or proxy coverage >=95%: {'PASS' if panel['float_market_cap_used'].notna().mean() >= .95 else 'FAIL'}.", f"- Expanded mode comparison rows: {len(comparison)}.", "", "Detailed factor comparisons are in `strict_vs_expanded_comparison.csv`; proxy and latest-snapshot limitations are intentionally retained rather than hidden."]
    (REPORT / "coverage_expansion_audit.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__": main()
