from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eot_drift import compute_eot_drift


PANEL_PATH = ROOT / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"
MEMBER_PANEL_PATH = ROOT / "data/processed/hs300_member_sample_20160101_20251231_baostock.parquet"
CLEAN_DAILY_PATH = ROOT / "data/processed/clean_daily_data.csv"
CALENDAR_PATH = ROOT / "data/raw/trade_calendar_20160101_20251231.parquet"
REPORT_DIR = ROOT / "reports/eot_factor_drift_feasibility"
FIG_DIR = REPORT_DIR / "figures"
PROCESSED_DIR = ROOT / "data/processed"

RANDOM_STATE = 42
BASE_WINDOW = 36
RECENT_WINDOW = 6
ICIR_WINDOW = 36
TOP_FRAC = 0.20

FACTOR_SPECS = {
    "reversal_1m": {
        "required_fields": "qfq_close",
        "notes": "Negative past 20-trading-day return.",
    },
    "momentum_3m": {
        "required_fields": "qfq_close",
        "notes": "Past 60-trading-day return.",
    },
    "volatility_1m": {
        "required_fields": "return_1d/qfq_close",
        "notes": "Negative 20-trading-day realized volatility.",
    },
    "turnover_1m": {
        "required_fields": "turnover",
        "notes": "Negative 20-trading-day average turnover.",
    },
    "liquidity_1m": {
        "required_fields": "amount",
        "notes": "log1p of 20-trading-day average amount; not size-neutralized.",
    },
    "size": {
        "required_fields": "market_cap",
        "notes": "Skipped because market capitalization is not available.",
    },
}
FACTOR_NAMES = [name for name in FACTOR_SPECS if name != "size"]


def ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    try:
        df.to_parquet(path, index=False, engine="fastparquet")
    except ImportError:
        df.to_parquet(path, index=False)


def safe_float(x: float | int | np.floating | None) -> float:
    if x is None or pd.isna(x):
        return float("nan")
    return float(x)


def fmt_pct(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "NA"
    return f"{100 * float(x):.2f}%"


def max_drawdown(returns: pd.Series) -> tuple[float, pd.Series]:
    nav = (1 + returns.fillna(0)).cumprod()
    peak = nav.cummax()
    drawdown = nav / peak - 1
    return float(drawdown.min()), drawdown


def summarize_file(path: Path, sample_csv_rows: int | None = None) -> dict:
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)), "exists": False}

    if path.suffix == ".parquet":
        df = read_parquet(path)
    elif path.suffix == ".csv":
        if sample_csv_rows:
            df = pd.read_csv(path, nrows=sample_csv_rows)
        else:
            df = pd.read_csv(path)
    else:
        return {"path": str(path.relative_to(ROOT)), "exists": True}

    date_col = "date" if "date" in df.columns else None
    if date_col:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        start_date = dates.min()
        end_date = dates.max()
    else:
        start_date = pd.NaT
        end_date = pd.NaT

    ticker_col = "ticker" if "ticker" in df.columns else None
    missing_rate = float(df.isna().mean().mean()) if len(df.columns) else 0.0
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": True,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "start_date": start_date,
        "end_date": end_date,
        "tickers": int(df[ticker_col].nunique()) if ticker_col else None,
        "missing_rate": missing_rate,
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


def build_data_inventory(panel: pd.DataFrame, file_summaries: list[dict]) -> None:
    scripts = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("*.py"))
    raw_files = sorted(p for p in (ROOT / "data/raw").glob("*") if p.is_file())
    market_files = sorted((ROOT / "data/raw/market").glob("*.parquet"))
    processed_files = sorted(p for p in (ROOT / "data/processed").glob("*") if p.is_file())

    active = panel[(panel["is_hs300_member"] == True) & (panel["trade_status"] == 1)]
    date_range = (panel["date"].min(), panel["date"].max())
    active_counts = active.groupby("date")["ticker"].nunique()

    lines = [
        "# EOT Factor Drift Feasibility - Data Inventory",
        "",
        "## 1. Directory Structure Summary",
        "",
        f"- Project root: `{ROOT}`",
        f"- Python scripts: {', '.join(f'`{s}`' for s in scripts) if scripts else 'None'}",
        f"- Raw root files: {len(raw_files)} files",
        f"- Raw market parquet files: {len(market_files)} files",
        f"- Processed files: {', '.join(f'`{p.relative_to(ROOT)}`' for p in processed_files)}",
        "",
        "## 2. Key Data Files",
        "",
        "| file | rows | columns | date range | tickers | missing rate | key columns |",
        "| --- | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for info in file_summaries:
        if not info.get("exists"):
            lines.append(f"| `{info['path']}` | NA | NA | missing | NA | NA | NA |")
            continue
        dates = "NA"
        if pd.notna(info.get("start_date")):
            dates = f"{info['start_date'].date()} to {info['end_date'].date()}"
        cols = ", ".join(info.get("column_names", [])[:12])
        if len(info.get("column_names", [])) > 12:
            cols += ", ..."
        lines.append(
            f"| `{info['path']}` | {info.get('rows', 'NA')} | {info.get('columns', 'NA')} | "
            f"{dates} | {info.get('tickers') or 'NA'} | {fmt_pct(info.get('missing_rate'))} | {cols} |"
        )

    lines += [
        "",
        "## 3. Main Panel Coverage",
        "",
        f"- Main panel date range: {date_range[0].date()} to {date_range[1].date()}",
        f"- Unique tickers in dynamic panel: {panel['ticker'].nunique()}",
        f"- Active HS300 member count per trading day: mean {active_counts.mean():.1f}, "
        f"min {active_counts.min()}, max {active_counts.max()}",
        f"- `qfq_close`, `amount`, `turnover`, `trade_status`, `is_st`, and `is_hs300_member` are available.",
        f"- Overall missing rate in main panel: {fmt_pct(panel.isna().mean().mean())}",
        "",
        "## 4. Currently Supported Factors",
        "",
        "- `reversal_1m`: supported by forward-adjusted close.",
        "- `momentum_3m`: supported by forward-adjusted close.",
        "- `volatility_1m`: supported by daily return / forward-adjusted close.",
        "- `turnover_1m`: supported by turnover.",
        "- `liquidity_1m`: supported by amount.",
        "",
        "## 5. Temporarily Unsupported Factors",
        "",
        "- `size`: market capitalization is not present in the current files.",
        "- Industry-neutral factors: industry classification is not present.",
        "- Value/quality factors: financial statement fields are not present.",
        "",
        "## 6. Feasibility for Monthly Testing and Backtest",
        "",
        "The current data can support a minimal monthly factor test, rolling drift diagnostics, "
        "and a preliminary stock-level long-only portfolio backtest over the HS300 dynamic universe. "
        "The test does not yet support industry/size neutralization, strict limit-up buy filters, "
        "or transaction-cost modeling.",
        "",
        "## 7. Main Data and Implementation Risks",
        "",
        "- Dynamic universe membership can introduce survivorship/constituent timing nuances if the original constituent source is imperfect.",
        "- No industry and market-cap fields means factor exposures are only winsorized and standardized, not neutralized.",
        "- No strict limit-up/limit-down buyability filter is available; `trade_status` and `is_st` are used as MVP filters.",
        "- EOT drift uses only monthly factor-performance observations; the 6-month recent window is small and noisy.",
        "- Transaction costs are ignored in the preliminary backtest.",
        "",
        "## 8. Reusable and New Code",
        "",
        "- Reusable: `scripts/research/factors/factors.py` contains basic return, reversal, momentum, volatility, liquidity, and turnover factor ideas.",
        "- New for this feasibility run: `src/eot_drift.py` and `scripts/research/eot/run_eot_factor_drift_feasibility.py`.",
        "",
    ]
    (REPORT_DIR / "data_inventory.md").write_text("\n".join(lines), encoding="utf-8")


def winsorize_zscore(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").astype(float)
    valid = x.dropna()
    if len(valid) < 30:
        return pd.Series(np.nan, index=s.index)
    lo, hi = valid.quantile([0.01, 0.99])
    x = x.clip(lo, hi)
    mean = x.mean()
    std = x.std(ddof=0)
    if not np.isfinite(std) or std <= 1e-12:
        return pd.Series(np.nan, index=s.index)
    return (x - mean) / std


def construct_monthly_factors(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.sort_values(["ticker", "date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    if "return_1d" not in df or df["return_1d"].isna().all():
        df["return_1d"] = df.groupby("ticker")["qfq_close"].pct_change()

    grouped = df.groupby("ticker", group_keys=False)
    df["reversal_1m"] = -grouped["qfq_close"].pct_change(20)
    df["momentum_3m"] = grouped["qfq_close"].pct_change(60)
    df["volatility_1m"] = -grouped["return_1d"].rolling(20, min_periods=15).std().reset_index(level=0, drop=True)
    df["turnover_1m"] = -grouped["turnover"].rolling(20, min_periods=15).mean().reset_index(level=0, drop=True)
    avg_amount = grouped["amount"].rolling(20, min_periods=15).mean().reset_index(level=0, drop=True)
    df["liquidity_1m"] = np.log1p(avg_amount)

    month_ends = df.groupby(df["date"].dt.to_period("M"))["date"].max().sort_values()
    monthly = df[df["date"].isin(month_ends.values)].copy()
    monthly = monthly.sort_values(["ticker", "date"])
    monthly["next_qfq_close"] = monthly.groupby("ticker")["qfq_close"].shift(-1)
    monthly["fwd_ret_1m"] = monthly["next_qfq_close"] / monthly["qfq_close"] - 1

    active_mask = (
        (monthly["is_hs300_member"] == True)
        & (monthly["trade_status"] == 1)
        & (monthly["is_st"].fillna(0).astype(int) == 0)
        & monthly["qfq_close"].gt(0)
    )
    monthly = monthly[active_mask].copy()

    for factor in FACTOR_NAMES:
        monthly[f"{factor}_z"] = monthly.groupby("date")[factor].transform(winsorize_zscore)

    return monthly


def factor_availability(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    active_counts = monthly.groupby("date")["ticker"].nunique()
    for factor, spec in FACTOR_SPECS.items():
        if factor == "size":
            rows.append(
                {
                    "factor_name": factor,
                    "required_fields": spec["required_fields"],
                    "available_or_not": False,
                    "start_date": pd.NaT,
                    "end_date": pd.NaT,
                    "coverage_ratio": 0.0,
                    "missing_ratio": 1.0,
                    "neutralized_or_not": False,
                    "notes": spec["notes"],
                }
            )
            continue
        valid = monthly[monthly[f"{factor}_z"].notna()]
        by_date_valid = valid.groupby("date")["ticker"].nunique()
        aligned = active_counts.to_frame("active").join(by_date_valid.rename("valid"), how="left").fillna(0)
        coverage = float((aligned["valid"] / aligned["active"]).mean())
        rows.append(
            {
                "factor_name": factor,
                "required_fields": spec["required_fields"],
                "available_or_not": len(valid) > 0,
                "start_date": valid["date"].min(),
                "end_date": valid["date"].max(),
                "coverage_ratio": coverage,
                "missing_ratio": 1.0 - coverage,
                "neutralized_or_not": False,
                "notes": spec["notes"] + " Winsorized and z-scored; no industry/size neutralization.",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(REPORT_DIR / "factor_availability.csv", index=False)
    return out


def compute_monthly_performance(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, g in monthly.groupby("date", sort=True):
        universe_n = g["ticker"].nunique()
        for factor in FACTOR_NAMES:
            fcol = f"{factor}_z"
            valid = g[["ticker", fcol, "fwd_ret_1m"]].dropna()
            coverage = len(valid) / universe_n if universe_n else 0.0
            if len(valid) < 50 or coverage < 0.50:
                continue
            rank_ic = valid[fcol].corr(valid["fwd_ret_1m"], method="spearman")
            q = max(int(math.floor(len(valid) * TOP_FRAC)), 1)
            top = valid.nlargest(q, fcol)
            bottom = valid.nsmallest(q, fcol)
            long_short = top["fwd_ret_1m"].mean() - bottom["fwd_ret_1m"].mean()
            rows.append(
                {
                    "date": date,
                    "factor_name": factor,
                    "rank_ic": rank_ic,
                    "long_short_return": long_short,
                    "top_return": top["fwd_ret_1m"].mean(),
                    "bottom_return": bottom["fwd_ret_1m"].mean(),
                    "downside_return": min(long_short, 0),
                    "n_stocks": len(valid),
                    "coverage_ratio": coverage,
                }
            )
    perf = pd.DataFrame(rows).sort_values(["date", "factor_name"]).reset_index(drop=True)
    write_parquet(perf, PROCESSED_DIR / "monthly_factor_performance.parquet")
    return perf


def summarize_performance(perf: pd.DataFrame, total_months: int) -> pd.DataFrame:
    rows = []
    for factor, g in perf.groupby("factor_name"):
        ls_std = g["long_short_return"].std(ddof=1)
        ic_std = g["rank_ic"].std(ddof=1)
        rows.append(
            {
                "factor_name": factor,
                "mean_rank_ic": g["rank_ic"].mean(),
                "std_rank_ic": ic_std,
                "icir": g["rank_ic"].mean() / ic_std if ic_std and np.isfinite(ic_std) else np.nan,
                "mean_long_short_return": g["long_short_return"].mean(),
                "std_long_short_return": ls_std,
                "t_stat_long_short": g["long_short_return"].mean() / (ls_std / math.sqrt(len(g)))
                if ls_std and np.isfinite(ls_std)
                else np.nan,
                "positive_month_ratio": (g["long_short_return"] > 0).mean(),
                "worst_month": g.loc[g["long_short_return"].idxmin(), "date"],
                "best_month": g.loc[g["long_short_return"].idxmax(), "date"],
                "missing_months": total_months - len(g),
                "available_months": len(g),
            }
        )
    out = pd.DataFrame(rows).sort_values("factor_name")
    out.to_csv(REPORT_DIR / "factor_performance_summary.csv", index=False)
    return out


def compute_drift_scores(perf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    features = ["rank_ic", "long_short_return", "downside_return"]
    for factor, g in perf.groupby("factor_name"):
        g = g.sort_values("date").reset_index(drop=True)
        for idx in range(BASE_WINDOW + RECENT_WINDOW, len(g)):
            base = g.loc[idx - BASE_WINDOW - RECENT_WINDOW : idx - RECENT_WINDOW - 1, features].to_numpy()
            recent = g.loc[idx - RECENT_WINDOW : idx - 1, features].to_numpy()
            date = g.loc[idx, "date"]
            try:
                result = compute_eot_drift(
                    base,
                    recent,
                    n_reference=100,
                    epsilon_scale=0.1,
                    random_state=RANDOM_STATE,
                )
                rows.append(
                    {
                        "date": date,
                        "factor_name": factor,
                        "eot_drift": result.drift,
                        "eot_drift_zscore": np.nan,
                        "mean_shift_norm": result.mean_shift_norm,
                        "covariance_shift_norm": result.covariance_shift_norm,
                        "n_base": result.n_base,
                        "n_recent": result.n_recent,
                        "epsilon": result.epsilon,
                        "n_reference": result.n_reference,
                        "status": result.status,
                        "notes": result.notes,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "date": date,
                        "factor_name": factor,
                        "eot_drift": np.nan,
                        "eot_drift_zscore": np.nan,
                        "mean_shift_norm": np.nan,
                        "covariance_shift_norm": np.nan,
                        "n_base": len(base),
                        "n_recent": len(recent),
                        "epsilon": np.nan,
                        "n_reference": 100,
                        "status": "error",
                        "notes": f"{type(exc).__name__}: {exc}",
                    }
                )
    drift = pd.DataFrame(rows).sort_values(["factor_name", "date"]).reset_index(drop=True)
    if not drift.empty:
        zscores = []
        for _, g in drift.groupby("factor_name", sort=False):
            prior_mean = g["eot_drift"].expanding(min_periods=6).mean().shift(1)
            prior_std = g["eot_drift"].expanding(min_periods=6).std(ddof=1).shift(1)
            z = (g["eot_drift"] - prior_mean) / prior_std.replace(0, np.nan)
            zscores.append(z.fillna(0.0))
        drift["eot_drift_zscore"] = pd.concat(zscores).sort_index()

    write_parquet(drift, PROCESSED_DIR / "eot_factor_drift_scores.parquet")
    return drift


def summarize_drift(drift: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor, g in drift.groupby("factor_name"):
        ok = g[g["eot_drift"].notna()].copy()
        if ok.empty:
            rows.append(
                {
                    "factor_name": factor,
                    "mean_eot_drift": np.nan,
                    "std_eot_drift": np.nan,
                    "max_eot_drift": np.nan,
                    "max_drift_month": pd.NaT,
                    "mean_shift_corr": np.nan,
                    "cov_shift_corr": np.nan,
                    "available_months": 0,
                    "notes": "; ".join(g["notes"].dropna().astype(str).unique()[:3]),
                }
            )
            continue
        rows.append(
            {
                "factor_name": factor,
                "mean_eot_drift": ok["eot_drift"].mean(),
                "std_eot_drift": ok["eot_drift"].std(ddof=1),
                "max_eot_drift": ok["eot_drift"].max(),
                "max_drift_month": ok.loc[ok["eot_drift"].idxmax(), "date"],
                "mean_shift_corr": ok["eot_drift"].corr(ok["mean_shift_norm"]),
                "cov_shift_corr": ok["eot_drift"].corr(ok["covariance_shift_norm"]),
                "available_months": len(ok),
                "notes": "; ".join(ok.loc[ok["status"] != "ok", "notes"].dropna().astype(str).unique()[:3]),
            }
        )
    out = pd.DataFrame(rows).sort_values("factor_name")
    out.to_csv(REPORT_DIR / "eot_drift_summary.csv", index=False)
    return out


def compute_factor_weights(perf: pd.DataFrame, drift: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(drift.loc[drift["eot_drift"].notna(), "date"].unique())
    drift_idx = drift.set_index(["date", "factor_name"])
    rows = []
    for date in dates:
        available = []
        icirs = {}
        penalties = {}
        drift_values = {}
        drift_z = {}
        for factor in FACTOR_NAMES:
            hist = perf[(perf["factor_name"] == factor) & (perf["date"] < date)].sort_values("date").tail(ICIR_WINDOW)
            if len(hist) < 12:
                continue
            ic_std = hist["rank_ic"].std(ddof=1)
            icir = hist["rank_ic"].mean() / ic_std if ic_std and np.isfinite(ic_std) else 0.0
            key = (date, factor)
            if key in drift_idx.index:
                drow = drift_idx.loc[key]
                dz = safe_float(drow["eot_drift_zscore"])
                dv = safe_float(drow["eot_drift"])
            else:
                dz = 0.0
                dv = np.nan
            penalty = 1.0 / (1.0 + max(dz, 0.0))
            available.append(factor)
            icirs[factor] = icir
            penalties[factor] = penalty
            drift_values[factor] = dv
            drift_z[factor] = dz

        if not available:
            continue
        equal_w = {f: 1.0 / len(available) for f in available}
        raw_icir = {f: max(icirs[f], 0.0) for f in available}
        if sum(raw_icir.values()) <= 0:
            icir_w = equal_w.copy()
        else:
            total = sum(raw_icir.values())
            icir_w = {f: raw_icir[f] / total for f in available}

        raw_eot = {f: max(icirs[f], 0.0) * penalties[f] for f in available}
        if sum(raw_eot.values()) <= 0:
            eot_w = equal_w.copy()
        else:
            total = sum(raw_eot.values())
            eot_w = {f: raw_eot[f] / total for f in available}

        for factor in available:
            rows.append(
                {
                    "date": date,
                    "factor_name": factor,
                    "weight_equal": equal_w[factor],
                    "weight_icir": icir_w[factor],
                    "weight_icir_eot": eot_w[factor],
                    "icir": icirs[factor],
                    "eot_drift": drift_values[factor],
                    "eot_drift_zscore": drift_z[factor],
                    "penalty": penalties[factor],
                }
            )
    weights = pd.DataFrame(rows).sort_values(["date", "factor_name"]).reset_index(drop=True)
    write_parquet(weights, PROCESSED_DIR / "monthly_factor_weights.parquet")
    return weights


def run_backtest(monthly: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    method_cols = {
        "equal": "weight_equal",
        "icir": "weight_icir",
        "icir_eot": "weight_icir_eot",
    }
    prev_holdings = {method: set() for method in method_cols}
    turnover_rows = []
    rows = []
    for date in sorted(weights["date"].unique()):
        g = monthly[monthly["date"] == date].copy()
        g = g[g["fwd_ret_1m"].notna()]
        if len(g) < 50:
            continue
        wdate = weights[weights["date"] == date].set_index("factor_name")
        row = {"date": date}
        for method, wcol in method_cols.items():
            score = pd.Series(0.0, index=g.index)
            valid_factor_count = pd.Series(0, index=g.index)
            for factor in FACTOR_NAMES:
                if factor not in wdate.index:
                    continue
                zcol = f"{factor}_z"
                if zcol not in g:
                    continue
                vals = g[zcol]
                mask = vals.notna()
                score.loc[mask] += vals.loc[mask] * float(wdate.loc[factor, wcol])
                valid_factor_count.loc[mask] += 1
            candidates = g.loc[valid_factor_count >= 3, ["ticker", "fwd_ret_1m"]].copy()
            candidates["score"] = score.loc[candidates.index]
            candidates = candidates.dropna()
            if len(candidates) < 50:
                row[f"ret_{method}"] = np.nan
                turnover_rows.append({"date": date, "strategy": method, "turnover": np.nan})
                continue
            q = max(int(math.floor(len(candidates) * TOP_FRAC)), 1)
            holdings = set(candidates.nlargest(q, "score")["ticker"].astype(str))
            ret = candidates[candidates["ticker"].astype(str).isin(holdings)]["fwd_ret_1m"].mean()
            if prev_holdings[method]:
                old_n = len(prev_holdings[method])
                new_n = len(holdings)
                overlap = len(prev_holdings[method] & holdings)
                turnover = 1.0 - overlap / max(old_n, new_n)
            else:
                turnover = 1.0
            prev_holdings[method] = holdings
            row[f"ret_{method}"] = ret
            turnover_rows.append({"date": date, "strategy": method, "turnover": turnover})
        rows.append(row)

    nav = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    for method in method_cols:
        nav[f"nav_{method}"] = (1 + nav[f"ret_{method}"].fillna(0)).cumprod()
    nav = nav[["date", "nav_equal", "nav_icir", "nav_icir_eot", "ret_equal", "ret_icir", "ret_icir_eot"]]
    write_parquet(nav, PROCESSED_DIR / "eot_factor_drift_backtest_nav.parquet")

    turnover = pd.DataFrame(turnover_rows)
    summary_rows = []
    display = {
        "equal": "Equal-factor multifactor",
        "icir": "ICIR-weighted multifactor",
        "icir_eot": "ICIR + EOT drift weighted multifactor",
    }
    for method in method_cols:
        ret = nav[f"ret_{method}"].dropna()
        if ret.empty:
            continue
        ann_return = (1 + ret).prod() ** (12 / len(ret)) - 1
        ann_vol = ret.std(ddof=1) * math.sqrt(12)
        sharpe = ret.mean() * 12 / ann_vol if ann_vol and np.isfinite(ann_vol) else np.nan
        mdd, _ = max_drawdown(ret)
        calmar = ann_return / abs(mdd) if mdd < 0 else np.nan
        avg_turnover = turnover[turnover["strategy"] == method]["turnover"].mean()
        summary_rows.append(
            {
                "strategy": display[method],
                "annual_return": ann_return,
                "annual_volatility": ann_vol,
                "sharpe": sharpe,
                "max_drawdown": mdd,
                "calmar": calmar,
                "monthly_win_rate": (ret > 0).mean(),
                "turnover": avg_turnover,
                "start_date": nav.loc[ret.index[0], "date"],
                "end_date": nav.loc[ret.index[-1], "date"],
                "notes": "Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only.",
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(REPORT_DIR / "preliminary_backtest_summary.csv", index=False)
    return nav, summary


def create_figures(perf: pd.DataFrame, drift: pd.DataFrame, weights: pd.DataFrame, nav: pd.DataFrame) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")

    def save_line(df: pd.DataFrame, y: str, title: str, filename: str) -> None:
        fig, ax = plt.subplots(figsize=(11, 6))
        for factor, g in df.groupby("factor_name"):
            ax.plot(g["date"], g[y], label=factor, linewidth=1.2)
        ax.axhline(0, color="black", linewidth=0.8, alpha=0.6)
        ax.set_title(title)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG_DIR / filename, dpi=160)
        plt.close(fig)

    save_line(perf, "rank_ic", "Monthly Rank IC", "rank_ic_timeseries.png")
    save_line(perf, "long_short_return", "Monthly Long-Short Return", "long_short_return_timeseries.png")
    save_line(drift[drift["status"].isin(["ok", "fallback"])], "eot_drift", "EOT Drift Score", "eot_drift_timeseries.png")

    fig, ax = plt.subplots(figsize=(11, 6))
    for col, label in [
        ("nav_equal", "Equal"),
        ("nav_icir", "ICIR"),
        ("nav_icir_eot", "ICIR + EOT"),
    ]:
        ax.plot(nav["date"], nav[col], label=label, linewidth=1.5)
    ax.set_title("Backtest NAV")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "strategy_nav.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    for ret_col, label in [
        ("ret_equal", "Equal"),
        ("ret_icir", "ICIR"),
        ("ret_icir_eot", "ICIR + EOT"),
    ]:
        _, dd = max_drawdown(nav[ret_col])
        ax.plot(nav["date"], dd.values, label=label, linewidth=1.5)
    ax.set_title("Backtest Drawdown")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "strategy_drawdown.png", dpi=160)
    plt.close(fig)

    if not weights.empty:
        fig, ax = plt.subplots(figsize=(11, 6))
        pivot = weights.pivot(index="date", columns="factor_name", values="weight_icir_eot").sort_index()
        pivot.plot(ax=ax, linewidth=1.3)
        ax.set_title("ICIR + EOT Factor Weights")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "factor_weights_icir_eot.png", dpi=160)
        plt.close(fig)

    merged = drift.merge(perf, on=["date", "factor_name"], how="left").sort_values(["factor_name", "date"])
    merged["next_3m_long_short"] = merged.groupby("factor_name")["long_short_return"].transform(
        lambda s: s.shift(-1).rolling(3, min_periods=1).mean()
    )
    scatter = merged.dropna(subset=["eot_drift_zscore", "next_3m_long_short"])
    if len(scatter) > 10:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(scatter["eot_drift_zscore"], scatter["next_3m_long_short"], alpha=0.65)
        ax.axhline(0, color="black", linewidth=0.8, alpha=0.6)
        ax.axvline(0, color="black", linewidth=0.8, alpha=0.6)
        ax.set_xlabel("EOT drift z-score")
        ax.set_ylabel("Next 3-month long-short return")
        ax.set_title("EOT Drift vs Future Factor Performance")
        fig.tight_layout()
        fig.savefig(FIG_DIR / "eot_vs_future_performance.png", dpi=160)
        plt.close(fig)


def create_final_report(
    availability: pd.DataFrame,
    perf_summary: pd.DataFrame,
    drift_summary: pd.DataFrame,
    backtest_summary: pd.DataFrame,
    perf: pd.DataFrame,
    drift: pd.DataFrame,
) -> None:
    best_ic = perf_summary.sort_values("icir", ascending=False).head(2)
    worst_ic = perf_summary.sort_values("icir", ascending=True).head(2)
    eot_status = drift["status"].value_counts(dropna=False).to_dict() if not drift.empty else {}
    bt = backtest_summary.set_index("strategy") if not backtest_summary.empty else pd.DataFrame()

    def metric(strategy: str, col: str) -> str:
        if bt.empty or strategy not in bt.index or pd.isna(bt.loc[strategy, col]):
            return "NA"
        val = bt.loc[strategy, col]
        if col in {"annual_return", "annual_volatility", "max_drawdown", "monthly_win_rate", "turnover"}:
            return fmt_pct(val)
        return f"{float(val):.3f}"

    eot_strategy = "ICIR + EOT drift weighted multifactor"
    icir_strategy = "ICIR-weighted multifactor"
    equal_strategy = "Equal-factor multifactor"
    if not bt.empty:
        best_sharpe = bt["sharpe"].astype(float).idxmax()
        eot_better_sharpe = (
            eot_strategy in bt.index
            and icir_strategy in bt.index
            and bt.loc[eot_strategy, "sharpe"] > bt.loc[icir_strategy, "sharpe"]
        )
    else:
        best_sharpe = "NA"
        eot_better_sharpe = False

    conclusion = "partially feasible"
    recommendation = (
        "EOT drift is worth continuing mainly as a monitoring signal, while direct penalty-based weighting "
        "needs more validation before becoming a production allocation rule."
    )

    lines = [
        "# EOT Factor Drift Feasibility Report",
        "",
        "## 1. Executive Summary",
        "",
        f"Judgment: **{conclusion}**.",
        "",
        "The current project has enough adjusted A-share daily price/volume data to build a minimum viable "
        "HS300 monthly factor evaluation loop, compute rolling EOT drift, and run a preliminary long-only "
        "multifactor backtest. It is not yet a complete research platform because industry, market-cap, "
        "strict limit-up/limit-down buyability, and transaction-cost data are missing.",
        "",
        "## 2. Data Availability",
        "",
        "- Forward-adjusted OHLC data, amount, turnover, trade status, ST flag, and dynamic HS300 membership are available.",
        "- The main panel spans 2016-01-04 to 2025-12-31, enough for 36-month base + 6-month recent rolling drift windows.",
        "- Industry, market capitalization, financial statement data, and strict limit-up/limit-down filtering are not available.",
        "- `quant` conda environment was used; POT and parquet support are required. Output uses `fastparquet` when available and otherwise falls back to the default pandas parquet engine.",
        "",
        "## 3. Factor Construction",
        "",
        "Constructed MVP factors: `reversal_1m`, `momentum_3m`, `volatility_1m`, `turnover_1m`, and `liquidity_1m`. "
        "All factors were winsorized and cross-sectionally standardized each rebalance month. Larger values are treated "
        "as higher expected future return. No industry or size neutralization was performed because those fields are absent.",
        "",
        "Availability snapshot:",
        "",
        availability.to_markdown(index=False),
        "",
        "## 4. Factor Performance",
        "",
        "Performance summary:",
        "",
        perf_summary.to_markdown(index=False),
        "",
        "The strongest factors by Rank ICIR in this run were "
        + ", ".join(best_ic["factor_name"].astype(str).tolist())
        + ". The weakest were "
        + ", ".join(worst_ic["factor_name"].astype(str).tolist())
        + ". Monthly long-short returns are visibly noisy, which is expected for a small HS300-only universe and simple price-volume factors.",
        "",
        "## 5. EOT Drift Diagnostics",
        "",
        f"EOT status counts: `{eot_status}`.",
        "",
        "EOT drift was stable enough to compute for the MVP windows. The drift series often co-moves with mean/covariance "
        "shift baselines, so the current evidence for uniquely incremental information is suggestive rather than conclusive. "
        "The 6-month recent window is small for distribution comparison; a weekly factor-performance panel would materially "
        "increase sample size and should be the next serious version. POT emitted occasional non-fatal Sinkhorn convergence "
        "warnings during the run; production use should log transport diagnostics and tune regularization/iteration settings.",
        "",
        "Drift summary:",
        "",
        drift_summary.to_markdown(index=False),
        "",
        "## 6. Preliminary Backtest",
        "",
        "Backtest summary:",
        "",
        backtest_summary.to_markdown(index=False),
        "",
        f"- Equal-factor Sharpe: {metric(equal_strategy, 'sharpe')}; max drawdown: {metric(equal_strategy, 'max_drawdown')}.",
        f"- ICIR Sharpe: {metric(icir_strategy, 'sharpe')}; max drawdown: {metric(icir_strategy, 'max_drawdown')}.",
        f"- ICIR + EOT Sharpe: {metric(eot_strategy, 'sharpe')}; max drawdown: {metric(eot_strategy, 'max_drawdown')}.",
        f"- Best Sharpe in this MVP: {best_sharpe}.",
        "",
        "This is a stock-level top-20% long-only test with equal-weight holdings. It ignores transaction costs and uses only "
        "`trade_status`/`is_st` filters, so the result should be interpreted as a feasibility signal, not a tradable claim.",
        "",
        "## 7. Interpretation",
        "",
        "Recommended interpretation: **factor failure monitoring indicator first, dynamic weighting penalty second**.",
        "",
        recommendation,
        "",
        "As a direct allocation penalty, EOT drift can overreact when the recent window has only six monthly observations. "
        f"In this run, the EOT penalty {'improved' if eot_better_sharpe else 'did not clearly improve'} Sharpe relative to plain ICIR weighting, "
        "so it should not yet be treated as a proven optimizer.",
        "",
        "## 8. Limitations",
        "",
        "- Monthly recent window has only 6 observations, making EOT noisy.",
        "- Factor universe is small and limited to price/volume signals.",
        "- No industry or size neutralization.",
        "- No transaction costs, slippage, or strict buyability filters.",
        "- No bootstrap or statistical significance testing.",
        "- Dynamic HS300 membership quality depends on the existing data source.",
        "- EOT drift may capture noisy performance distribution changes rather than persistent regime shifts.",
        "- A-share style cycles can make conclusions unstable across subperiods.",
        "",
        "## 9. Recommendation",
        "",
        "It is worth continuing, especially as a resume-friendly research project, but the next iteration should be framed "
        "as risk monitoring and factor lifecycle diagnostics rather than a finished trading system. Recommended next steps:",
        "",
        "1. Add industry and market-cap data, then rerun neutralized factors.",
        "2. Build weekly factor-performance observations to make EOT windows less noisy.",
        "3. Add transaction costs and stricter limit-up/limit-down filters.",
        "4. Test EOT drift as a monitoring dashboard signal before using it as an allocation penalty.",
        "5. Add bootstrap/permutation tests around drift spikes and subsequent performance deterioration.",
        "",
        "Resume wording suggestion: `Built an A-share multifactor research prototype that monitors factor performance distribution drift using entropic optimal transport and evaluates drift-aware dynamic factor weighting on a HS300 monthly backtest.`",
        "",
        "## Deliverables",
        "",
        "- `reports/eot_factor_drift_feasibility/data_inventory.md`",
        "- `reports/eot_factor_drift_feasibility/factor_availability.csv`",
        "- `data/processed/monthly_factor_performance.parquet`",
        "- `reports/eot_factor_drift_feasibility/factor_performance_summary.csv`",
        "- `src/eot_drift.py`",
        "- `data/processed/eot_factor_drift_scores.parquet`",
        "- `reports/eot_factor_drift_feasibility/eot_drift_summary.csv`",
        "- `data/processed/monthly_factor_weights.parquet`",
        "- `reports/eot_factor_drift_feasibility/preliminary_backtest_summary.csv`",
        "- `data/processed/eot_factor_drift_backtest_nav.parquet`",
        "- `reports/eot_factor_drift_feasibility/figures/`",
        "",
    ]
    (REPORT_DIR / "eot_factor_drift_feasibility_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    panel = read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])

    file_summaries = [
        summarize_file(PANEL_PATH),
        summarize_file(MEMBER_PANEL_PATH),
        summarize_file(CLEAN_DAILY_PATH, sample_csv_rows=200_000),
        summarize_file(CALENDAR_PATH),
    ]
    build_data_inventory(panel, file_summaries)

    monthly = construct_monthly_factors(panel)
    availability = factor_availability(monthly)
    perf = compute_monthly_performance(monthly)
    total_months = monthly["date"].nunique() - 1
    perf_summary = summarize_performance(perf, total_months)
    drift = compute_drift_scores(perf)
    drift_summary = summarize_drift(drift)
    weights = compute_factor_weights(perf, drift)
    nav, backtest_summary = run_backtest(monthly, weights)
    create_figures(perf, drift, weights, nav)
    create_final_report(availability, perf_summary, drift_summary, backtest_summary, perf, drift)

    print("Generated feasibility outputs under:")
    print(REPORT_DIR)
    print(PROCESSED_DIR / "monthly_factor_performance.parquet")
    print(PROCESSED_DIR / "eot_factor_drift_scores.parquet")
    print(PROCESSED_DIR / "monthly_factor_weights.parquet")
    print(PROCESSED_DIR / "eot_factor_drift_backtest_nav.parquet")


if __name__ == "__main__":
    main()
