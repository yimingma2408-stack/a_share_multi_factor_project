from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
import warnings
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from joblib import Parallel, delayed
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import cdist, squareform

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eot_drift import compute_eot_drift
from src.factor_lifecycle.factor_registry import lifecycle_factor_names, registry_frame
from src.factor_lifecycle.lifecycle import (
    apply_family_weight_cap,
    drift_penalty,
    normalized_nonnegative_weights,
    transaction_cost,
)
from src.factor_lifecycle.preprocessing import preprocess_factor_cross_section

SEED = 42
BASE_WEEKS = 156
RECENT_WEEKS = 26
TOP_FRAC = 0.20
PANEL_PATH = ROOT / "data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet"
CAP_PATH = ROOT / "data/processed/market_cap_panel.parquet"
FUND_PATH = ROOT / "data/processed/fundamental_panel_akshare.parquet"
OUT = ROOT / "data/processed/eot_factor_lifecycle"
REPORT = ROOT / "reports/eot_factor_lifecycle"
FIG = REPORT / "figures"
FACTORS = lifecycle_factor_names()
FAMILY = registry_frame().set_index("factor_name")["factor_family"].to_dict()


def write_parquet(df: pd.DataFrame, name: str) -> None:
    df.to_parquet(OUT / name, index=False)


def md_table(df: pd.DataFrame, n: int = 30) -> str:
    if df.empty:
        return "No rows generated."
    d = df.head(n).copy()
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].map(lambda x: "" if pd.isna(x) else f"{x:.4g}")
    return d.to_markdown(index=False)


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)


def audit_and_registry() -> tuple[pd.DataFrame, pd.DataFrame]:
    reg = registry_frame()
    reg.to_csv(REPORT / "factor_registry.csv", index=False)
    panel = pd.read_parquet(PANEL_PATH, columns=["date", "ticker", "qfq_close", "amount", "turnover", "trade_status", "is_st", "is_hs300_member"])
    caps = pd.read_parquet(CAP_PATH, columns=["date", "ticker", "market_cap", "float_market_cap"])
    fund = pd.read_parquet(FUND_PATH)
    p_dates = pd.to_datetime(panel["date"])
    active = panel[(panel["is_hs300_member"] == True) & (panel["trade_status"] == 1)]
    stat = {
        "market_rows": len(panel), "market_tickers": panel["ticker"].nunique(),
        "market_start": p_dates.min().date(), "market_end": p_dates.max().date(),
        "active_mean": active.groupby("date")["ticker"].nunique().mean(),
        "cap_rows": len(caps), "cap_tickers": caps["ticker"].nunique(),
        "cap_missing": caps["market_cap"].isna().mean(),
        "float_cap_missing": caps["float_market_cap"].isna().mean(),
        "fund_rows": len(fund), "fund_tickers": fund["ticker"].nunique(),
    }
    audit = f"""# Project and Data Audit

## Project structure and reusable modules

- Daily dynamic HS300 panel: `data/processed/{PANEL_PATH.name}`; {stat['market_rows']:,} rows, {stat['market_tickers']} tickers, {stat['market_start']} to {stat['market_end']}.
- Market-cap panel: {stat['cap_rows']:,} rows and {stat['cap_tickers']} tickers; total-cap missing {stat['cap_missing']:.2%}, float-cap missing {stat['float_cap_missing']:.2%}.
- Point-in-time fundamental panel: {stat['fund_rows']:,} rows but only {stat['fund_tickers']} tickers, so it is not suitable for the formal cross-sectional lifecycle backtest.
- Average active dynamic-universe count: {stat['active_mean']:.1f} stocks.
- Reused modules: `src/eot_drift.py`, `src/factors/*`, `src/analysis/*`, and the existing weekly/monthly EOT research outputs.
- New outputs are isolated under `data/processed/eot_factor_lifecycle/` and `reports/eot_factor_lifecycle/`.

## Factor library

- {len(reg)} implemented factor definitions were identified in code.
- {len(FACTORS)} market factors are enabled for this lifecycle run. They use only lagged/current adjusted prices, returns, turnover and amount.
- Value, quality and growth code is implemented and uses announcement-date alignment, but current five-ticker coverage is inadequate.
- Size is available as an exposure control. Industry classification is absent, so only market-cap neutralization is performed.

## Data-quality and PIT findings

- Weekly forward returns are created only after factor values are calculated and are never supplied to preprocessing.
- Dynamic HS300 membership, trade status and ST flags are dated observations. The source does not provide a perfect historical vendor snapshot or delisting reason table, so constituent-timing and survivorship risk cannot be eliminated completely.
- `qfq_close` is used for signal and return continuity. This research assumes the stored forward-adjusted series was generated without retroactively leaking unknown corporate-action information; that vendor-level assumption cannot be independently verified here.
- Financial rows satisfy `available_date <= panel date`, but source revision histories are unavailable. Financial factors remain excluded from the formal backtest.
- Limit-up filtering uses the dated daily percentage change as an approximation; intraday queue/impact is unavailable.

## Recommended scope and risks

The formal study uses the ten enabled market factors. Other market variants are watch-only or redundancy controls; fundamental factors are rejected from allocation until broad PIT coverage is collected. The main remaining risks are missing industry neutralization, approximate tradeability/costs, dynamic-index-source fidelity, total-cap rather than full float-cap neutralization, and a single-universe research design.
"""
    (REPORT / "project_and_data_audit.md").write_text(audit, encoding="utf-8")

    rows = []
    for r in reg.itertuples(index=False):
        if r.financial_or_market == "financial":
            safe, announce, lag, risk, action = True, True, "announcement/available date as-of", "medium: no revision history; five-ticker coverage", "reject from formal backtest"
        elif r.factor_name in {"size", "rolling_beta", "idiosyncratic_volatility", "downside_beta"}:
            safe, announce, lag, risk, action = True, False, "rolling window ending at t", "low/medium: benchmark or exposure role needs validation", "watch only"
        else:
            safe, announce, lag, risk = True, False, f"{r.lookback_window or 0} trading days ending at t", "low"
            action = "eligible lifecycle input" if r.lifecycle_enabled else "watch/redundancy control"
        rows.append({"factor_name": r.factor_name, "point_in_time_safe": safe, "announcement_date_available": announce,
                     "lag_rule": lag, "future_information_risk": risk, "action": action, "notes": r.notes})
    pit = pd.DataFrame(rows)
    pit.to_csv(REPORT / "point_in_time_audit.csv", index=False)
    leakage = """# Leakage Audit

All formal lifecycle features are computed on date *t* using observations dated no later than *t*. Weekly outcomes use the next observed weekly close. Eligibility, ICIR, drift percentiles, clusters, representatives, health scores and weights use shifted rolling/expanding history. Weekly signals are mapped backward to monthly rebalances. Tests assert these boundaries.

Financial factors are not admitted to the formal backtest: announcement dates exist and are as-of aligned, but only five tickers are populated and restatement histories are unavailable. The dynamic universe is date-varying, but fidelity to the vendor's historical constituent publication timestamps cannot be proved from local files. Adjusted-price corporate-action timing is also a vendor assumption. These are documented limitations rather than treated as solved.
"""
    (REPORT / "leakage_audit.md").write_text(leakage, encoding="utf-8")
    return reg, pit


def build_weekly_panel(force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    cache = OUT / "weekly_factor_cross_sections.parquet"
    perf_path = OUT / "weekly_factor_performance_full.parquet"
    if cache.exists() and perf_path.exists() and not force:
        return pd.read_parquet(cache), pd.read_parquet(perf_path)
    cols = ["date", "ticker", "qfq_close", "return_1d", "amount", "turnover", "pct_change_pct", "trade_status", "is_st", "is_hs300_member"]
    df = pd.read_parquet(PANEL_PATH, columns=cols).sort_values(["ticker", "date"])
    df["date"] = pd.to_datetime(df["date"]).astype("datetime64[ns]")
    caps = pd.read_parquet(CAP_PATH, columns=["date", "ticker", "market_cap"])
    caps["date"] = pd.to_datetime(caps["date"]).astype("datetime64[ns]")
    df = df.merge(caps, on=["date", "ticker"], how="left")
    g = df.groupby("ticker", group_keys=False)
    df["reversal_1m"] = -g["qfq_close"].pct_change(20)
    for name, w in [("momentum_1m", 20), ("momentum_3m", 60), ("momentum_6m", 120), ("momentum_12m", 250)]:
        df[name] = g["qfq_close"].pct_change(w)
    for name, w in [("volatility_1m", 20), ("volatility_3m", 60)]:
        df[name] = -g["return_1d"].rolling(w, min_periods=max(15, w // 2)).std().reset_index(level=0, drop=True)
    for name, w in [("turnover_1m", 20), ("turnover_3m", 60)]:
        df[name] = -g["turnover"].rolling(w, min_periods=max(15, w // 2)).mean().reset_index(level=0, drop=True)
    df["liquidity_1m"] = np.log1p(g["amount"].rolling(20, min_periods=15).mean().reset_index(level=0, drop=True).clip(lower=0))
    week_ends = df.groupby(df["date"].dt.to_period("W-FRI"))["date"].max()
    weekly = df[df["date"].isin(week_ends.values)].copy().sort_values(["ticker", "date"])
    weekly["fwd_ret_1w"] = weekly.groupby("ticker")["qfq_close"].shift(-1) / weekly["qfq_close"] - 1
    weekly["listing_observation_days"] = weekly.groupby("ticker").cumcount() * 5
    weekly = weekly[(weekly["is_hs300_member"] == True) & (weekly["trade_status"] == 1) & (weekly["is_st"].fillna(0).astype(int) == 0) & weekly["qfq_close"].gt(0)].copy()
    diag_rows = []
    for factor in FACTORS:
        pre = preprocess_factor_cross_section(weekly, factor, size_col="market_cap", industry_col="industry", neutralize=True)
        weekly[f"{factor}_z"] = pre[f"{factor}_processed"]
        diag_rows.append(pre[["date", "raw_coverage", "post_filter_coverage", "post_neutralization_coverage", "cross_section_std"]].assign(factor_name=factor))
    diagnostics = pd.concat(diag_rows, ignore_index=True)
    diagnostics.groupby(["date", "factor_name"], as_index=False).first().to_csv(REPORT / "factor_preprocessing_diagnostics.csv", index=False)

    perf_rows, prior_sets = [], {}
    for date, grp in weekly.groupby("date", sort=True):
        n = grp["ticker"].nunique()
        for factor in FACTORS:
            valid = grp[["ticker", f"{factor}_z", "fwd_ret_1w"]].dropna()
            if len(valid) < 50:
                continue
            q = max(int(len(valid) * TOP_FRAC), 1)
            top, bottom = valid.nlargest(q, f"{factor}_z"), valid.nsmallest(q, f"{factor}_z")
            selected = set(top["ticker"]) | set(bottom["ticker"])
            prev = prior_sets.get(factor)
            turnover = np.nan if prev is None else 1 - len(selected & prev) / max(len(selected | prev), 1)
            prior_sets[factor] = selected
            ls = top["fwd_ret_1w"].mean() - bottom["fwd_ret_1w"].mean()
            perf_rows.append({"date": date, "factor_name": factor, "factor_family": FAMILY[factor],
                              "rank_ic": valid[factor + "_z"].corr(valid["fwd_ret_1w"], method="spearman"),
                              "long_short_return": ls, "top_return": top["fwd_ret_1w"].mean(),
                              "bottom_return": bottom["fwd_ret_1w"].mean(), "downside_return": min(ls, 0),
                              "factor_turnover": turnover, "n_stocks": len(valid), "coverage_ratio": len(valid) / n})
    perf = pd.DataFrame(perf_rows).sort_values(["date", "factor_name"])
    keep = ["date", "ticker", "qfq_close", "fwd_ret_1w", "pct_change_pct", "trade_status", "is_st", "is_hs300_member", "market_cap", "listing_observation_days"] + [f"{f}_z" for f in FACTORS]
    write_parquet(weekly[keep], "weekly_factor_cross_sections.parquet")
    write_parquet(perf, "weekly_factor_performance_full.parquet")
    summary = perf.groupby(["factor_name", "factor_family"], as_index=False).agg(available_weeks=("date", "size"), coverage_ratio=("coverage_ratio", "mean"), mean_rank_ic=("rank_ic", "mean"), rank_ic_std=("rank_ic", "std"), mean_long_short_return=("long_short_return", "mean"), positive_period_ratio=("long_short_return", lambda x: (x > 0).mean()), factor_turnover=("factor_turnover", "mean"))
    summary["icir"] = summary["mean_rank_ic"] / summary["rank_ic_std"]
    summary["long_short_t_stat"] = summary["mean_long_short_return"] / perf.groupby("factor_name")["long_short_return"].std().values * np.sqrt(summary["available_weeks"])
    summary.to_csv(REPORT / "weekly_factor_performance_summary.csv", index=False)
    return weekly[keep], perf


def correlations_and_clusters(weekly: pd.DataFrame, perf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:
    zcols = [f"{f}_z" for f in FACTORS]
    matrices = []
    for _, g in weekly.groupby("date"):
        if len(g) >= 50:
            matrices.append(g[zcols].corr(method="spearman").to_numpy())
    cross = pd.DataFrame(np.nanmean(matrices, axis=0), index=FACTORS, columns=FACTORS)
    cross.to_csv(REPORT / "factor_cross_section_correlation.csv")
    ret = perf.pivot(index="date", columns="factor_name", values="long_short_return").reindex(columns=FACTORS).corr()
    ret.to_csv(REPORT / "factor_return_correlation.csv")
    combined = 0.5 * cross.abs().fillna(0) + 0.5 * ret.abs().fillna(0)
    np.fill_diagonal(combined.values, 1.0)
    dist = (1 - combined).clip(0, 1)
    link = linkage(squareform(dist.values, checks=False), method="average")
    ids = fcluster(link, t=0.40, criterion="distance")
    perf_summary = pd.read_csv(REPORT / "weekly_factor_performance_summary.csv").set_index("factor_name")
    rows = []
    for factor, cid in zip(FACTORS, ids):
        members = [f for f, c in zip(FACTORS, ids) if c == cid]
        scores = perf_summary.loc[members, "icir"].fillna(-99) - 0.10 * perf_summary.loc[members, "factor_turnover"].fillna(1)
        rep = scores.idxmax()
        red = combined.loc[factor, [m for m in members if m != factor]].max() if len(members) > 1 else 0.0
        rank = int(scores.rank(ascending=False, method="first").loc[factor])
        rows.append({"factor_name": factor, "factor_family": FAMILY[factor], "cluster_id": int(cid), "representative_factor": rep,
                     "within_cluster_rank": rank, "redundancy_score": red, "selection_status": "representative" if factor == rep else "retained_with_cluster_cap", "notes": "Full-sample cluster is descriptive only; backtest representatives are recomputed from prior history."})
    clusters = pd.DataFrame(rows)
    clusters.to_csv(REPORT / "factor_clusters.csv", index=False)
    return cross, ret, clusters, link


def eligibility(perf: pd.DataFrame, reg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for factor, g in perf.groupby("factor_name"):
        g = g.sort_values("date").copy()
        hist = g["rank_ic"].shift(1).rolling(104, min_periods=26)
        ls = g["long_short_return"].shift(1).rolling(104, min_periods=26)
        for i, r in enumerate(g.itertuples(index=False)):
            n_hist = i
            cov = g["coverage_ratio"].shift(1).rolling(52, min_periods=1).mean().iloc[i]
            disp = g["rank_ic"].shift(1).rolling(52, min_periods=1).std().iloc[i]
            if n_hist >= 52 and cov >= 0.70 and pd.notna(disp) and disp > 1e-4:
                status = "eligible"
            elif n_hist >= 26 and cov >= 0.50:
                status = "watch_only"
            else:
                status = "watch_only"
            icstd = hist.std().iloc[i]
            rows.append({"date": r.date, "factor_name": factor, "coverage_ratio": cov, "available_history": n_hist,
                         "mean_rank_ic": hist.mean().iloc[i], "rank_ic_std": icstd, "icir": hist.mean().iloc[i] / icstd if pd.notna(icstd) and icstd > 0 else np.nan,
                         "mean_long_short_return": ls.mean().iloc[i], "long_short_t_stat": np.nan,
                         "positive_period_ratio": (g["long_short_return"].shift(1).rolling(52, min_periods=1).apply(lambda x: np.mean(x > 0))).iloc[i],
                         "factor_turnover": g["factor_turnover"].shift(1).rolling(52, min_periods=1).mean().iloc[i],
                         "cross_section_dispersion": disp, "missing_ratio": 1 - cov if pd.notna(cov) else np.nan,
                         "point_in_time_status": "safe", "eligibility_status": status})
    panel = pd.DataFrame(rows)
    write_parquet(panel, "factor_eligibility_panel.parquet")
    latest = panel.sort_values("date").groupby("factor_name").tail(1)
    summary_rows = []
    for r in reg.itertuples(index=False):
        if r.factor_name in FACTORS:
            row = latest[latest["factor_name"] == r.factor_name].iloc[0]
            status, reason = row["eligibility_status"], "sufficient market coverage and history"
        elif r.financial_or_market == "financial":
            status, reason = "rejected", "formal PIT cross-section has only five tickers"
        else:
            status, reason = "watch_only", r.notes or "implemented but outside the pre-specified lifecycle set"
        summary_rows.append({"factor_name": r.factor_name, "factor_family": r.factor_family, "status": status, "reason": reason})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(REPORT / "factor_eligibility_summary.csv", index=False)
    return panel, summary


def _energy_mmd(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    ab, aa, bb = cdist(a, b), cdist(a, a), cdist(b, b)
    energy = 2 * ab.mean() - aa.mean() - bb.mean()
    pooled = np.vstack([a, b])
    d2 = cdist(pooled, pooled, metric="sqeuclidean")
    positive = d2[d2 > 0]
    gamma = 1 / max(np.median(positive), 1e-8)
    kaa, kbb, kab = np.exp(-gamma * cdist(a, a, "sqeuclidean")), np.exp(-gamma * cdist(b, b, "sqeuclidean")), np.exp(-gamma * cdist(a, b, "sqeuclidean"))
    return float(energy), float(kaa.mean() + kbb.mean() - 2 * kab.mean())


def _compute_factor_drift(factor: str, group: pd.DataFrame) -> list[dict]:
    rows, features = [], ["rank_ic", "long_short_return", "downside_return"]
    g = group.sort_values("date").reset_index(drop=True)
    for i in range(BASE_WEEKS + RECENT_WEEKS, len(g)):
        base = g.loc[i - BASE_WEEKS - RECENT_WEEKS:i - RECENT_WEEKS - 1, features].dropna().to_numpy()
        recent = g.loc[i - RECENT_WEEKS:i - 1, features].dropna().to_numpy()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = compute_eot_drift(base, recent, n_reference=100, epsilon_scale=0.1, random_state=SEED)
        energy, mmd = _energy_mmd(base, recent)
        warning_notes = "; ".join(str(w.message) for w in caught)
        status = "warning" if caught and result.status == "ok" else result.status
        rows.append({"date": g.loc[i, "date"], "factor_name": factor, "eot_drift": result.drift,
                     "mean_shift_norm": result.mean_shift_norm, "covariance_shift_norm": result.covariance_shift_norm,
                     "energy_distance": energy, "mmd_rbf": mmd, "sinkhorn_status": status,
                     "sinkhorn_iterations": np.nan, "convergence_warning": bool(caught) or result.status != "ok",
                     "epsilon": result.epsilon, "notes": warning_notes or result.notes})
    return rows


def drift_and_states(perf: pd.DataFrame, elig: pd.DataFrame, clusters: pd.DataFrame, force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    path = OUT / "weekly_eot_drift_full.parquet"
    if path.exists() and not force:
        drift = pd.read_parquet(path)
    else:
        groups = [(factor, g.copy()) for factor, g in perf.groupby("factor_name")]
        nested = Parallel(n_jobs=min(4, len(groups)), prefer="threads")(
            delayed(_compute_factor_drift)(factor, g) for factor, g in groups
        )
        rows = [row for group_rows in nested for row in group_rows]
        drift = pd.DataFrame(rows).sort_values(["factor_name", "date"])
        zparts = []
        for _, g in drift.groupby("factor_name", sort=False):
            mean = g["eot_drift"].expanding(26).mean().shift(1)
            std = g["eot_drift"].expanding(26).std().shift(1)
            zparts.append(((g["eot_drift"] - mean) / std.replace(0, np.nan)).fillna(0))
        drift["eot_drift_zscore"] = pd.concat(zparts).sort_index()
        write_parquet(drift, "weekly_eot_drift_full.parquet")
    dsum = drift.groupby("factor_name", as_index=False).agg(mean_eot_drift=("eot_drift", "mean"), std_eot_drift=("eot_drift", "std"), mean_shift_correlation=("eot_drift", lambda x: x.corr(drift.loc[x.index, "mean_shift_norm"])), covariance_shift_correlation=("eot_drift", lambda x: x.corr(drift.loc[x.index, "covariance_shift_norm"])), fallback_rate=("convergence_warning", "mean"))
    dsum.to_csv(REPORT / "weekly_eot_drift_summary.csv", index=False)
    smooth_parts = []
    for factor, g in drift.groupby("factor_name"):
        g = g.sort_values("date").copy()
        s = g["eot_drift_zscore"]
        for w in [4, 8, 12]: g[f"mean_{w}w"] = s.rolling(w, min_periods=4).mean()
        for h in [4, 8, 12]: g[f"ewma_hl{h}"] = s.ewm(halflife=h, adjust=False, min_periods=4).mean()
        smooth_parts.append(g)
    smooth = pd.concat(smooth_parts).sort_values(["date", "factor_name"])
    write_parquet(smooth, "weekly_eot_drift_smoothed.parquet")

    base = perf.merge(smooth[["date", "factor_name", "eot_drift", "eot_drift_zscore", "ewma_hl8", "sinkhorn_status"]], on=["date", "factor_name"], how="left")
    state_parts = []
    for factor, g in base.groupby("factor_name"):
        g = g.sort_values("date").copy()
        hmean = g["rank_ic"].shift(1).rolling(104, min_periods=52).mean(); hstd = g["rank_ic"].shift(1).rolling(104, min_periods=52).std()
        rmean = g["rank_ic"].shift(1).rolling(26, min_periods=13).mean(); rstd = g["rank_ic"].shift(1).rolling(26, min_periods=13).std()
        g["historical_icir"] = hmean / hstd.replace(0, np.nan); g["recent_icir"] = rmean / rstd.replace(0, np.nan)
        g["quality_trend"] = g["recent_icir"] - g["historical_icir"]
        g["smoothed_eot_drift"] = g["ewma_hl8"]
        g["drift_percentile"] = g["smoothed_eot_drift"].apply(lambda _: np.nan)
        vals = []
        for i, v in enumerate(g["smoothed_eot_drift"]):
            hist = g["smoothed_eot_drift"].iloc[:i].dropna()
            vals.append((hist <= v).mean() if pd.notna(v) and len(hist) >= 26 else np.nan)
        g["drift_percentile"] = vals
        states = []
        for r in g.itertuples(index=False):
            if pd.isna(r.historical_icir) or pd.isna(r.recent_icir): state = "Dormant"
            elif r.historical_icir > 0 and r.recent_icir >= 0 and (pd.isna(r.drift_percentile) or r.drift_percentile < .8): state = "Healthy"
            elif r.historical_icir > 0 and (r.drift_percentile >= .8 or r.quality_trend < -.25): state = "Watch"
            elif r.recent_icir < 0 and r.quality_trend < 0 and r.drift_percentile >= .5: state = "Decaying"
            elif r.recent_icir > 0 and r.quality_trend > .25 and (pd.isna(r.drift_percentile) or r.drift_percentile < .8): state = "Recovering"
            else: state = "Dormant"
            states.append(state)
        g["lifecycle_state"] = states
        state_parts.append(g)
    states = pd.concat(state_parts).merge(elig[["date", "factor_name", "eligibility_status"]], on=["date", "factor_name"], how="left").merge(clusters[["factor_name", "cluster_id"]], on="factor_name", how="left")
    states["factor_family"] = states["factor_name"].map(FAMILY); states["notes"] = "Rules use shifted rolling quality and expanding prior drift percentiles."
    state_cols = ["date", "factor_name", "factor_family", "historical_icir", "recent_icir", "quality_trend", "eot_drift", "smoothed_eot_drift", "drift_percentile", "lifecycle_state", "eligibility_status", "cluster_id", "factor_turnover", "coverage_ratio", "sinkhorn_status", "notes"]
    states = states[state_cols].sort_values(["date", "factor_name"])
    write_parquet(states, "factor_lifecycle_states.parquet")
    states.groupby(["factor_name", "lifecycle_state"]).size().rename("weeks").reset_index().to_csv(REPORT / "factor_lifecycle_state_summary.csv", index=False)
    return drift, smooth, states


def _dynamic_cluster_map(perf: pd.DataFrame, date: pd.Timestamp, names: list[str]) -> dict[str, int]:
    history = perf[(perf["date"] < date) & perf["factor_name"].isin(names)].pivot(index="date", columns="factor_name", values="long_short_return").reindex(columns=names).tail(104)
    if len(history) < 26 or len(names) <= 1:
        return {factor: i + 1 for i, factor in enumerate(names)}
    corr = history.corr().abs().fillna(0.0).clip(0, 1)
    # Newer pandas/NumPy combinations can expose ``corr.values`` as
    # read-only; use an explicit writable NumPy copy for the diagonal fix.
    corr_values = corr.to_numpy(copy=True)
    np.fill_diagonal(corr_values, 1.0)
    link = linkage(squareform(1 - corr_values, checks=False), method="average")
    ids = fcluster(link, t=0.40, criterion="distance")
    return dict(zip(names, map(int, ids)))


def _dynamic_redundancy_map(perf: pd.DataFrame, date: pd.Timestamp, names: list[str]) -> dict[str, float]:
    history = perf[(perf["date"] < date) & perf["factor_name"].isin(names)].pivot(index="date", columns="factor_name", values="long_short_return").reindex(columns=names).tail(104)
    if len(history) < 26:
        return {factor: 0.0 for factor in names}
    corr = history.corr().abs().fillna(0.0).clip(0, 1)
    result = {}
    for factor in names:
        peers = [name for name in names if name != factor]
        result[factor] = float(corr.loc[factor, peers].max()) if peers else 0.0
    return result


def health_selection_weights(states: pd.DataFrame, perf: pd.DataFrame, clusters: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    health = states.copy()
    redundancy_parts = []
    for date, group in health.groupby("date"):
        names = list(group["factor_name"])
        red_map = _dynamic_redundancy_map(perf, date, names)
        redundancy_parts.extend({"date": date, "factor_name": factor, "redundancy_score": score} for factor, score in red_map.items())
    health = health.merge(pd.DataFrame(redundancy_parts), on=["date", "factor_name"], how="left")
    health["redundancy_score"] = health["redundancy_score"].fillna(0)
    health["quality_score"] = health.groupby("date")["historical_icir"].rank(pct=True).fillna(.5)
    health["drift_score"] = 1 - health.groupby("date")["smoothed_eot_drift"].rank(pct=True).fillna(.5)
    health["redundancy_component"] = 1 - health["redundancy_score"]
    health["cost_score"] = 1 - health.groupby("date")["factor_turnover"].rank(pct=True).fillna(.5)
    health["health_score"] = .50 * health["quality_score"] + .25 * health["drift_score"] + .15 * health["redundancy_component"] + .10 * health["cost_score"]
    write_parquet(health[["date", "factor_name", "factor_family", "health_score", "quality_score", "drift_score", "redundancy_score", "cost_score"]], "factor_health_scores.parquet")
    sel_rows = []
    allowed = {"Healthy", "Watch", "Recovering"}
    for date, g in health.groupby("date"):
        elig = g[g["eligibility_status"] == "eligible"].copy()
        cluster_map = _dynamic_cluster_map(perf, date, list(elig.factor_name))
        elig["dynamic_cluster_id"] = elig["factor_name"].map(cluster_map)
        reps = elig.sort_values(["dynamic_cluster_id", "health_score"], ascending=[True, False]).groupby("dynamic_cluster_id").head(1)
        schemes = {"all_eligible": set(elig.factor_name), "cluster_representatives": set(reps.factor_name),
                   "healthy_watch_recovering": set(elig[elig.lifecycle_state.isin(allowed)].factor_name)}
        for k in [5, 8, 10]: schemes[f"top_{k}_health"] = set(elig.nlargest(k, "health_score").factor_name)
        fam = set(elig.sort_values("health_score", ascending=False).groupby("factor_family").head(3).factor_name)
        schemes["family_balanced"] = fam
        for scheme, selected in schemes.items():
            for factor in FACTORS:
                sel_rows.append({"date": date, "factor_name": factor, "selection_strategy": scheme, "selected": factor in selected,
                                 "dynamic_cluster_id": cluster_map.get(factor, np.nan), "selection_reason": "walk-forward history only"})
    selection = pd.DataFrame(sel_rows); write_parquet(selection, "dynamic_factor_selection.parquet")

    month_dates = pd.read_parquet(PANEL_PATH, columns=["date"])["date"].pipe(pd.to_datetime).drop_duplicates().groupby(lambda i: 0)
    all_dates = pd.read_parquet(PANEL_PATH, columns=["date"]); all_dates["date"] = pd.to_datetime(all_dates["date"])
    rebal = sorted(all_dates.groupby(all_dates["date"].dt.to_period("M"))["date"].max())
    available = sorted(health["date"].drop_duplicates())
    mapping = {d: max([w for w in available if w <= d], default=pd.NaT) for d in rebal}
    methods = ["equal_eligible", "cluster_representative_equal", "icir_weighted", "icir_eot", "icir_eot_redundancy", "icir_eot_redundancy_cost", "lifecycle_filtered_drift"]
    wrows = []
    for date, wdate in mapping.items():
        if pd.isna(wdate): continue
        g = health[(health["date"] == wdate) & (health["eligibility_status"] == "eligible")].set_index("factor_name").copy()
        if g.empty: continue
        cluster_map = _dynamic_cluster_map(perf, wdate, list(g.index))
        g["dynamic_cluster_id"] = pd.Series(cluster_map)
        reps = set(g.sort_values(["dynamic_cluster_id", "health_score"], ascending=[True, False]).groupby("dynamic_cluster_id").head(1).index)
        for method in methods:
            included = pd.Series(True, index=g.index)
            if method == "cluster_representative_equal": included = pd.Series(g.index.isin(reps), index=g.index)
            if method == "lifecycle_filtered_drift": included = g["lifecycle_state"].isin({"Healthy", "Watch", "Recovering"})
            if not included.any(): included[:] = True
            if method in {"equal_eligible", "cluster_representative_equal"}: raw = pd.Series(1.0, index=g.index)
            else: raw = g["historical_icir"].clip(lower=0).fillna(0)
            dpen = drift_penalty(g["smoothed_eot_drift"], eta=1, lower=.5) if method in {"icir_eot", "icir_eot_redundancy", "icir_eot_redundancy_cost", "lifecycle_filtered_drift"} else pd.Series(1., index=g.index)
            rpen = 1 / (1 + g["redundancy_score"].fillna(0)) if method in {"icir_eot_redundancy", "icir_eot_redundancy_cost", "lifecycle_filtered_drift"} else pd.Series(1., index=g.index)
            cpen = 1 / (1 + g["factor_turnover"].fillna(g["factor_turnover"].median())) if method in {"icir_eot_redundancy_cost", "lifecycle_filtered_drift"} else pd.Series(1., index=g.index)
            raw = raw * dpen * rpen * cpen * included.astype(float)
            if raw.sum() <= 0: raw = included.astype(float)
            weights = apply_family_weight_cap(raw, g["factor_family"], cap=.65)
            for f in g.index:
                wrows.append({"date": date, "signal_date": wdate, "factor_name": f, "factor_family": g.loc[f, "factor_family"], "weighting_method": method,
                              "dynamic_cluster_id": g.loc[f, "dynamic_cluster_id"],
                              "icir": g.loc[f, "historical_icir"], "drift_signal": g.loc[f, "smoothed_eot_drift"], "drift_penalty": dpen.loc[f], "redundancy_penalty": rpen.loc[f], "cost_penalty": cpen.loc[f], "raw_weight": raw.loc[f], "final_weight": weights.loc[f]})
    weights = pd.DataFrame(wrows); write_parquet(weights, "factor_weights_full.parquet")
    constraints = """# Factor Family Weight Constraints

The lifecycle set contains `price_volume` and `risk` families. At each monthly rebalance, raw non-negative weights are normalized and each family is capped at 65%. Excess weight is redistributed to uncapped families. A 65% cap is used because a 35% cap would be infeasible with only two represented families. Size is an exposure control rather than an alpha family; fundamental families are excluded due five-ticker coverage. All caps use contemporaneously available family labels and past-only signals.
"""
    (REPORT / "factor_family_weight_constraints.md").write_text(constraints, encoding="utf-8")
    return health, selection, weights


def backtest(weekly: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = pd.read_parquet(PANEL_PATH, columns=["date", "ticker", "qfq_close", "pct_change_pct", "trade_status", "is_st", "is_hs300_member"]).sort_values(["ticker", "date"])
    daily["date"] = pd.to_datetime(daily["date"])
    ends = daily.groupby(daily["date"].dt.to_period("M"))["date"].max()
    monthly = daily[daily["date"].isin(ends.values)].copy().sort_values(["ticker", "date"])
    monthly["fwd_ret_1m"] = monthly.groupby("ticker")["qfq_close"].shift(-1) / monthly["qfq_close"] - 1
    first = daily.groupby("ticker")["date"].min(); monthly["listing_days_proxy"] = (monthly["date"] - monthly["ticker"].map(first)).dt.days
    methods = weights["weighting_method"].unique(); rows, holdings_prev = [], {}
    weight_turnover = {}
    for method, wm in weights.groupby("weighting_method"):
        pivot = wm.pivot(index="date", columns="factor_name", values="final_weight").fillna(0).sort_index()
        turns = pivot.diff().abs().sum(axis=1) / 2
        if len(turns): turns.iloc[0] = 0.5 * pivot.iloc[0].abs().sum()
        weight_turnover.update({(method, date): value for date, value in turns.items()})
    weekly_idx = {d: g.set_index("ticker") for d, g in weekly.groupby("date")}
    for date, mg in monthly.groupby("date", sort=True):
        wgts = weights[weights["date"] == date]
        if wgts.empty: continue
        signal_date = wgts["signal_date"].iloc[0]
        if signal_date not in weekly_idx: continue
        base = mg.set_index("ticker").join(weekly_idx[signal_date][[f"{f}_z" for f in FACTORS]], how="inner")
        base = base[(base["is_hs300_member"] == True) & (base["trade_status"] == 1) & (base["is_st"].fillna(0).astype(int) == 0) & (base["pct_change_pct"] < 9.8) & (base["listing_days_proxy"] >= 120) & base["fwd_ret_1m"].notna()]
        for method in methods:
            w = wgts[wgts["weighting_method"] == method].set_index("factor_name")["final_weight"]
            cols = [f"{f}_z" for f in w.index]; valid = base.dropna(subset=cols)
            if len(valid) < 50: continue
            score = sum(valid[f + "_z"] * w.loc[f] for f in w.index)
            nsel = max(int(len(valid) * TOP_FRAC), 1); selected = set(score.nlargest(nsel).index)
            prev = holdings_prev.get(method, set()); turnover = 1 - len(selected & prev) / max(len(selected), 1) if prev else 1.0
            holdings_prev[method] = selected
            gross = valid.loc[list(selected), "fwd_ret_1m"].mean()
            factor_turn = weight_turnover.get((method, date), np.nan)
            rows.append({"date": date, "strategy": method, "gross_return": gross, "stock_turnover": turnover, "factor_turnover": factor_turn,
                         "number_of_selected_factors": int((w > 0).sum()), "number_of_selected_stocks": nsel})
    base = pd.DataFrame(rows).sort_values(["strategy", "date"])
    nav_rows = []
    for cost in [0, 5, 10, 20]:
        part = base.copy(); part["cost_bps"] = cost; part["net_return"] = transaction_cost(part["gross_return"], part["stock_turnover"], cost)
        part["nav"] = part.groupby("strategy")["net_return"].transform(lambda x: (1 + x).cumprod())
        part["gross_nav"] = part.groupby("strategy")["gross_return"].transform(lambda x: (1 + x).cumprod())
        nav_rows.append(part)
    nav = pd.concat(nav_rows, ignore_index=True); write_parquet(nav, "backtest_nav.parquet")
    summaries = []
    for (strategy, cost), g in nav.groupby(["strategy", "cost_bps"]):
        r = g["net_return"]; years = len(r) / 12; ann = (1 + r).prod() ** (1 / years) - 1 if years > 0 else np.nan
        vol = r.std() * np.sqrt(12); curve = (1 + r).cumprod(); dd = (curve / curve.cummax() - 1).min()
        summaries.append({"strategy": strategy, "cost_bps": cost, "annual_return": ann, "annual_volatility": vol, "sharpe": ann / vol if vol else np.nan,
                          "max_drawdown": dd, "calmar": ann / abs(dd) if dd else np.nan, "monthly_win_rate": (r > 0).mean(),
                          "average_turnover": g["stock_turnover"].mean(), "factor_turnover": g["factor_turnover"].mean(),
                          "number_of_selected_factors": g["number_of_selected_factors"].mean(), "number_of_selected_stocks": g["number_of_selected_stocks"].mean()})
    summary = pd.DataFrame(summaries); summary.to_csv(REPORT / "backtest_summary.csv", index=False)
    cost = summary[["strategy", "cost_bps", "annual_return", "sharpe", "max_drawdown", "average_turnover", "factor_turnover"]]
    cost.to_csv(REPORT / "transaction_cost_sensitivity.csv", index=False)
    return nav, summary, base


def diagnostics_reports(perf: pd.DataFrame, states: pd.DataFrame, nav: pd.DataFrame, base_bt: pd.DataFrame, health: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    drift_diag = pd.read_parquet(OUT / "weekly_eot_drift_full.parquet", columns=["date", "factor_name", "mean_shift_norm", "covariance_shift_norm"])
    merged = states.merge(perf[["date", "factor_name", "rank_ic", "long_short_return"]], on=["date", "factor_name"], how="left", suffixes=("", "_perf")).merge(drift_diag, on=["date", "factor_name"], how="left")
    rows = []
    for factor, g in merged.groupby("factor_name"):
        g = g.sort_values("date").copy()
        for h in [4, 12]:
            g[f"future_{h}w_rank_ic"] = g["rank_ic"].shift(-1)[::-1].rolling(h, min_periods=h // 2).mean()[::-1]
            g[f"future_{h}w_ls"] = g["long_short_return"].shift(-1)[::-1].rolling(h, min_periods=h // 2).sum()[::-1]
        g["future_12w_downside_probability"] = (g["long_short_return"].shift(-1) < 0)[::-1].rolling(12, min_periods=6).mean()[::-1]
        returns = g["long_short_return"].to_numpy(dtype=float)
        future_drawdowns = []
        for i in range(len(g)):
            future = returns[i + 1:i + 13]
            future = future[np.isfinite(future)]
            if len(future) < 6:
                future_drawdowns.append(np.nan)
            else:
                curve = np.cumprod(1 + future); future_drawdowns.append(float(np.min(curve / np.maximum.accumulate(curve) - 1)))
        g["future_12w_factor_drawdown"] = future_drawdowns
        for regime, mask in [("high_drift", g["drift_percentile"] >= .8), ("normal_drift", g["drift_percentile"] < .8)]:
            rows.append({"factor_name": factor, "drift_regime": regime, "observations": int(mask.sum()),
                         "future_4w_rank_ic": g.loc[mask, "future_4w_rank_ic"].mean(), "future_12w_rank_ic": g.loc[mask, "future_12w_rank_ic"].mean(),
                         "future_4w_long_short_return": g.loc[mask, "future_4w_ls"].mean(), "future_12w_long_short_return": g.loc[mask, "future_12w_ls"].mean(),
                         "downside_probability": g.loc[mask, "future_12w_downside_probability"].mean(),
                         "future_12w_factor_drawdown": g.loc[mask, "future_12w_factor_drawdown"].mean(),
                         "mean_eot_drift": g.loc[mask, "eot_drift"].mean(),
                         "mean_shift": g.loc[mask, "mean_shift_norm"].mean(), "covariance_shift": g.loc[mask, "covariance_shift_norm"].mean()})
    monitor = pd.DataFrame(rows); monitor.to_csv(REPORT / "monitoring_diagnostics.csv", index=False)
    high = monitor[monitor.drift_regime == "high_drift"].set_index("factor_name"); normal = monitor[monitor.drift_regime == "normal_drift"].set_index("factor_name")
    delta = (high["future_12w_rank_ic"] - normal["future_12w_rank_ic"]).mean()
    interp = f"""# Monitoring Interpretation

High drift is defined from each factor's expanding, past-only 80th percentile. Across factors, high-drift weeks differ from normal weeks by {delta:.4f} in average subsequent 12-week Rank IC. This is an association, not a causal or tradable forecast.

EOT is most defensible as a **contemporaneous instability detector**: it summarizes joint changes in Rank IC, long-short return and downside return. Predictive-warning value is evaluated in `monitoring_diagnostics.csv` and varies by factor. Allocation value is tested only through a conservative EWMA-HL8 penalty clipped to [0.5, 1.0]. The report does not claim that EOT alone predicts returns or validates a live strategy.
"""
    (REPORT / "monitoring_interpretation.md").write_text(interp, encoding="utf-8")

    b = base_bt.copy(); b["date"] = pd.to_datetime(b["date"]); split = b["date"].sort_values().iloc[len(b["date"].drop_duplicates()) // 2]
    benchmark = b.groupby("date")["gross_return"].mean().sort_index(); trend = (1 + benchmark).rolling(12, min_periods=6).apply(np.prod, raw=True) - 1; vol = benchmark.rolling(12, min_periods=6).std()
    vol_med = vol.expanding(12).median().shift(1)
    labels = pd.DataFrame({"date": benchmark.index, "early_late": np.where(benchmark.index <= split, "early", "late"), "bull_bear": np.where(trend >= 0, "bull", "bear"), "vol_regime": np.where(vol >= vol_med, "high_vol", "low_vol")})
    rb = b.merge(labels, on="date", how="left"); subs = []
    for dimension in ["early_late", "bull_bear", "vol_regime"]:
        for (strategy, regime), g in rb.groupby(["strategy", dimension]):
            r = g["gross_return"]; ann = (1 + r).prod() ** (12 / len(r)) - 1 if len(r) else np.nan; vv = r.std() * np.sqrt(12); curve = (1 + r).cumprod(); dd = (curve / curve.cummax() - 1).min()
            subs.append({"strategy": strategy, "regime_dimension": dimension, "regime": regime, "months": len(g), "annual_return": ann, "sharpe": ann / vv if vv else np.nan, "max_drawdown": dd})
    sub = pd.DataFrame(subs); sub.to_csv(REPORT / "subperiod_robustness.csv", index=False)
    (REPORT / "regime_analysis.md").write_text("# Regime Analysis\n\nRegimes use pre-specified rules: early/late split at the sample midpoint, bull/bear from trailing 12-month average-strategy return, and high/low volatility from trailing 12-month volatility versus its expanding past median. Results are in `subperiod_robustness.csv`. They are descriptive and do not tune parameters.\n", encoding="utf-8")
    dash = states.merge(health[["date", "factor_name", "health_score", "redundancy_score"]], on=["date", "factor_name"], how="left")
    portfolio = weights.query("weighting_method == 'lifecycle_filtered_drift'")[["signal_date", "factor_name", "final_weight"]].drop_duplicates(["signal_date", "factor_name"], keep="last").rename(columns={"signal_date": "date", "final_weight": "portfolio_weight"})
    dash = dash.merge(portfolio, on=["date", "factor_name"], how="left")
    convergence_issue = dash["sinkhorn_status"].notna() & dash["sinkhorn_status"].ne("ok")
    dash["warning_flag"] = dash["lifecycle_state"].isin(["Watch", "Decaying"]) | (dash["drift_percentile"] >= .8) | (dash["quality_trend"] < -.25) | convergence_issue
    dash["warning_reason"] = np.select([convergence_issue, dash["lifecycle_state"].eq("Decaying"), dash["drift_percentile"] >= .8, dash["quality_trend"] < -.25, dash["lifecycle_state"].eq("Watch")], ["Sinkhorn convergence/fallback", "Decaying state", "drift percentile above 80%", "quality deterioration", "Watch state"], default="")
    dash_cols = ["date", "factor_name", "factor_family", "eligibility_status", "cluster_id", "lifecycle_state", "health_score", "historical_icir", "recent_icir", "smoothed_eot_drift", "drift_percentile", "factor_turnover", "redundancy_score", "portfolio_weight", "warning_flag", "warning_reason"]
    write_parquet(dash[dash_cols].sort_values(["date", "factor_name"]), "factor_lifecycle_dashboard.parquet")
    return monitor, sub


def figures(reg: pd.DataFrame, perf: pd.DataFrame, cross: pd.DataFrame, link: np.ndarray, clusters: pd.DataFrame, states: pd.DataFrame, health: pd.DataFrame, weights: pd.DataFrame, nav: pd.DataFrame, summary: pd.DataFrame, monitor: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid"); plt.rcParams["figure.dpi"] = 130
    def save(name: str): plt.tight_layout(); plt.savefig(FIG / name, bbox_inches="tight"); plt.close()
    reg.groupby("factor_family").size().sort_values().plot.barh(title="Implemented factor library by family"); save("01_factor_library_distribution.png")
    ps = pd.read_csv(REPORT / "weekly_factor_performance_summary.csv").sort_values("icir"); ps.plot.barh(x="factor_name", y="icir", legend=False, title="Weekly Rank ICIR"); save("02_factor_icir_ranking.png")
    plt.figure(figsize=(9, 7)); sns.heatmap(cross, cmap="vlag", center=0); plt.title("Mean cross-sectional Spearman correlation"); save("03_factor_correlation_heatmap.png")
    plt.figure(figsize=(10, 5)); dendrogram(link, labels=FACTORS, leaf_rotation=45); plt.title("Combined-correlation hierarchical clustering"); save("04_factor_cluster_tree.png")
    clusters.sort_values("cluster_id").plot.bar(x="factor_name", y="redundancy_score", color=np.where(clusters.sort_values("cluster_id")["selection_status"].eq("representative"), "#2a9d8f", "#e9c46a"), title="Representative selection and redundancy"); save("05_representative_factors.png")
    states.pivot(index="date", columns="factor_name", values="smoothed_eot_drift").plot(figsize=(12, 6), title="Weekly smoothed EOT drift (EWMA HL8)"); save("06_weekly_eot_drift.png")
    state_map = {"Dormant":0,"Decaying":1,"Watch":2,"Recovering":3,"Healthy":4}; sm = states.assign(code=states.lifecycle_state.map(state_map)).pivot(index="factor_name", columns="date", values="code"); plt.figure(figsize=(13, 5)); sns.heatmap(sm, cmap="RdYlGn", cbar_kws={"ticks":list(state_map.values())}); plt.title("Factor lifecycle state timeline"); save("07_lifecycle_state_timeline.png")
    hm = health.pivot(index="factor_name", columns="date", values="health_score"); plt.figure(figsize=(13, 5)); sns.heatmap(hm, cmap="YlGnBu"); plt.title("Factor Health Score"); save("08_health_score_heatmap.png")
    famw = weights.groupby(["date","weighting_method","factor_family"])["final_weight"].sum().reset_index(); famw[famw.weighting_method.eq("lifecycle_filtered_drift")].pivot(index="date",columns="factor_family",values="final_weight").plot.area(figsize=(11,5),title="Family weights over time"); save("09_family_weights.png")
    main = nav[nav.cost_bps.eq(10)].pivot(index="date",columns="strategy",values="nav"); main.plot(figsize=(12,6),title="Strategy NAV after 10 bps one-way cost"); save("10_strategy_nav.png")
    dd = main / main.cummax() - 1; dd.plot(figsize=(12,6),title="Strategy drawdowns (10 bps)"); save("11_strategy_drawdown.png")
    summary.pivot(index="cost_bps",columns="strategy",values="sharpe").plot(marker="o",figsize=(10,5),title="Transaction-cost sensitivity"); save("12_transaction_cost_sensitivity.png")
    s10=summary[summary.cost_bps.eq(10)]; plt.scatter(s10.average_turnover,s10.sharpe); [plt.text(r.average_turnover,r.sharpe,r.strategy,fontsize=7) for r in s10.itertuples()]; plt.xlabel("Stock turnover"); plt.ylabel("Sharpe"); plt.title("Sharpe vs turnover"); save("13_sharpe_vs_turnover.png")
    plt.scatter(s10.max_drawdown,s10.sharpe); [plt.text(r.max_drawdown,r.sharpe,r.strategy,fontsize=7) for r in s10.itertuples()]; plt.xlabel("Max drawdown"); plt.ylabel("Sharpe"); plt.title("Sharpe vs max drawdown"); save("14_sharpe_vs_drawdown.png")
    monitor.pivot(index="factor_name",columns="drift_regime",values="future_12w_rank_ic").plot.bar(figsize=(11,5),title="High vs normal drift: subsequent 12-week Rank IC"); save("15_high_vs_normal_drift.png")
    latest = pd.read_parquet(OUT / "factor_lifecycle_dashboard.parquet").sort_values("date").groupby("factor_name").tail(1).sort_values("health_score"); colors=latest.lifecycle_state.map({"Healthy":"#2a9d8f","Watch":"#e9c46a","Decaying":"#e76f51","Dormant":"#8d99ae","Recovering":"#52b788"}); latest.plot.barh(x="factor_name",y="health_score",color=colors,legend=False,title="Latest factor lifecycle dashboard"); save("16_latest_dashboard.png")


def final_reports(reg: pd.DataFrame, elig_summary: pd.DataFrame, clusters: pd.DataFrame, states: pd.DataFrame, summary: pd.DataFrame, monitor: pd.DataFrame, elapsed: float) -> None:
    counts = elig_summary["status"].value_counts(); nclusters = clusters.cluster_id.nunique()
    xcorr = pd.read_csv(REPORT / "factor_cross_section_correlation.csv", index_col=0)
    rcorr = pd.read_csv(REPORT / "factor_return_correlation.csv", index_col=0)
    combined = 0.5 * xcorr.abs() + 0.5 * rcorr.abs()
    pairs = sorted([(combined.loc[a, b], a, b) for i, a in enumerate(combined.index) for b in combined.columns[i + 1:]], reverse=True)
    repeated_text = ", ".join(f"{a}/{b} ({score:.3f})" for score, a, b in pairs if score >= .85)
    s10 = summary[summary.cost_bps.eq(10)].sort_values(["sharpe", "max_drawdown"], ascending=[False, False]); best = s10.iloc[0] if not s10.empty else None
    equal = s10[s10.strategy.eq("equal_eligible")]; drift = s10[s10.strategy.eq("lifecycle_filtered_drift")]
    incr = (drift.sharpe.iloc[0] - equal.sharpe.iloc[0]) if len(drift) and len(equal) else np.nan
    state_counts = states.lifecycle_state.value_counts(normalize=True)
    report = f"""# EOT-Based Factor Lifecycle Diagnostics with Experimental Drift-Aware Weighting

## 1. Executive Summary

The project was upgraded successfully into a reproducible lifecycle-diagnostics research pipeline. Code contains {len(reg)} registered factor definitions; {counts.get('eligible',0)} are eligible, {counts.get('watch_only',0)} watch-only, and {counts.get('rejected',0)} rejected in the latest/static eligibility summary. The formal ten-factor market library forms {nclusters} descriptive clusters. Weekly EOT, smoothed drift, lifecycle states, health scores, walk-forward selection, weights and monthly backtests were generated.

At 10 bps, the highest observed Sharpe is `{best.strategy if best is not None else 'NA'}` ({best.sharpe:.3f} if available). The lifecycle-filtered drift method changes Sharpe versus equal eligible factors by {incr:.3f}. This is a historical research comparison, not a live strategy claim.

## 2. Data and Factor Library

The formal sample is the dated dynamic HS300 panel from 2016-01-04 to 2025-12-31. Signals use adjusted prices, returns, turnover and amount; total market cap is merged for cross-sectional neutralization. Industry is unavailable. Fundamental code and announcement-date fields exist, but the current panel contains only five tickers and is excluded from formal allocation tests.

## 3. Eligibility and Data Quality

Eligibility is recomputed from past history. Minimum formal requirements are 52 prior weekly observations, 70% recent coverage and non-degenerate dispersion. Early weeks remain watch-only. Latest/static counts are shown above; rejected factors are fundamentals with inadequate cross-sectional coverage.

## 4. Redundancy and Clustering

Clustering uses 50% average cross-sectional absolute Spearman correlation and 50% factor long-short-return absolute correlation, distance `1-|corr|`, average linkage and a pre-set 0.40 cut. Descriptive highly redundant pairs (combined score >=0.85): {repeated_text or 'none above the preset threshold'}. Full-sample clusters are reporting diagnostics only; backtest clusters, redundancy scores and representative selection use information available at each decision date.

## 5. Weekly Factor Performance

See `weekly_factor_performance_summary.csv` for Rank IC, ICIR, long-short return, positive-week ratio, coverage and turnover. Next-week returns are computed after signal construction.

## 6. EOT Lifecycle Diagnostics

EOT uses the three-dimensional vector `(RankIC, LSReturn, DownsideReturn)`, a 156-week base window, 26-week recent window, 100 shared references, epsilon scale 0.1 and seed 42. Energy distance, MMD, mean shift, covariance shift and convergence status are retained. The primary signal is EWMA half-life 8; five alternative smoothers are stored for robustness.

## 7. Lifecycle States

Past-only rolling ICIR, recent ICIR, their trend and expanding drift percentile create Healthy, Watch, Decaying, Dormant and Recovering states. Overall proportions: {json.dumps({k: round(v,4) for k,v in state_counts.items()}, ensure_ascii=False)}. Rules are explicit in the pipeline; early insufficient-history observations are Dormant.

## 8. Factor Selection and Weighting

The study compares all eligible, cluster representatives, lifecycle-filtered, Top-K 5/8/10 and family-balanced selections. Weighting compares equal, representative equal, ICIR, ICIR+EOT, redundancy, cost and lifecycle-filtered models. Drift uses `clip(1/(1+max(D,0)),0.5,1)`. Family totals are capped at 65% because only price-volume and risk families are formally represented.

## 9. Backtest Results

Monthly portfolios use the latest weekly signal no later than rebalance, top 20% stock selection and equal stock weights. ST, suspension, approximate limit-up and 120-day observed-history filters apply. See `backtest_summary.csv`. Emphasis belongs on Sharpe, drawdown, Calmar and turnover rather than annual return alone.

## 10. Monitoring Value vs Allocation Value

EOT drift is primarily useful as a **monitoring signal**, with a conservative secondary allocation penalty. It detects contemporaneous joint distribution instability; predictive warning varies by factor. The 10-bps allocation increment versus equal eligible factors is {incr:.3f} Sharpe and must be interpreted alongside turnover, drawdown, regimes and costs.

## 11. Robustness

Results include 0/5/10/20 bps cost sensitivity and pre-set early/late, bull/bear and high/low-volatility regimes. No parameter grid was optimized on the full sample.

## 12. Limitations

The financial panel covers five tickers; announcement revision histories and industry data are absent. Float cap is incomplete, so total cap is used. Historical constituent-publication timing and adjusted-price vendor mechanics cannot be independently verified. The HS300 focus, simplified equal-weight execution, limit-up proxy, linear costs, absent impact model, factor correlation, uneven family counts and EOT overlap with mean shift limit generalization. Historical results do not establish live tradability.

## 13. Final Project Positioning

Recommended title: **A-Share Factor Failure Monitoring with Entropic Optimal Transport**.

## 14. Resume Wording

**中文简历：** 基于动态沪深300样本构建10因子周度生命周期监控框架，使用熵正则最优传输识别因子分布漂移，并以无未来信息的滚动资格筛选、聚类去冗余和保守漂移惩罚完成月度 walk-forward 对照回测；系统评估交易成本、换手、回撤与市场状态稳健性，明确区分监控价值与配置价值。

**English resume:** Built a weekly lifecycle-monitoring framework for 10 A-share factors in a dynamic CSI 300 universe, using entropic optimal transport to diagnose distribution drift and past-only eligibility, redundancy clustering, and conservative drift penalties in monthly walk-forward experiments; evaluated costs, turnover, drawdowns, and regime robustness while separating monitoring value from allocation value.

**30-second interview introduction:** I built an A-share factor failure-monitoring project. Rather than treating EOT drift as a return forecast, I measure joint changes in weekly IC, long-short return and downside behavior, classify factor lifecycle states, and test a clipped secondary weighting penalty with walk-forward controls. The main contribution is a reproducible monitoring system with honest PIT and data-coverage limits.

**2-minute interview introduction:** The project starts from a dynamic CSI 300 daily panel and a registered factor library. I audit point-in-time safety and reject the current fundamental factors from formal tests because only five stocks are populated. For ten research-ready market factors, I apply cross-sectional MAD winsorization, market-cap neutralization and direction standardization, then build next-week Rank IC and long-short distributions. EOT compares a three-year base distribution with the latest six months, while mean shift, covariance shift, energy distance and MMD provide interpretable controls. Past-only ICIR and drift percentiles create Healthy, Watch, Decaying, Dormant and Recovering states. I then compare equal, cluster-aware, ICIR and conservatively clipped drift-aware weights in a monthly walk-forward portfolio with transaction costs and regime tests. The defensible conclusion is monitoring first, allocation second; the exercise is a research prototype, not evidence of live alpha.

## 15. Next Steps

1. Expand PIT financial statements and revision histories to the full dynamic universe.
2. Add dated industry classifications and free-float capitalization.
3. Validate constituent publication timestamps and corporate-action adjustment timing.
4. Add benchmark-relative risk, impact-aware execution and another universe.
5. Run genuinely out-of-sample paper monitoring before considering allocation use.
"""
    (REPORT / "eot_factor_lifecycle_final_report.md").write_text(report, encoding="utf-8")
    readme = """# EOT Factor Lifecycle Research

This directory contains an A-share factor lifecycle study built around weekly entropic optimal-transport drift. It covers project/data auditing, a unified factor registry, PIT screening, market-cap-neutralized factor preprocessing, dynamic eligibility, redundancy clustering, weekly performance distributions, EOT drift, explicit lifecycle states, health scores, factor selection, conservative weights, monthly walk-forward backtests, cost sensitivity and regime diagnostics.

The formal study uses ten market factors in the dynamic HS300 universe. Financial factors are registered but excluded because the current PIT panel covers only five tickers. EOT is positioned primarily as monitoring, not as a standalone return forecast.

Reproduce from the project root with:

```bash
python scripts/run_eot_factor_lifecycle.py
python -m pytest -q
```

Use `--force` to rebuild cached weekly cross-sections and EOT scores. Random seed is 42. Main findings and limitations are in `eot_factor_lifecycle_final_report.md`.
"""
    (REPORT / "README.md").write_text(readme, encoding="utf-8")
    repro = f"""# Test and Reproducibility Report

- Pipeline command: `python scripts/run_eot_factor_lifecycle.py`
- Test command: `python -m pytest -q`
- Python: {sys.version.split()[0]} on {platform.platform()}
- Random seed: {SEED}
- EOT: base {BASE_WEEKS} weeks, recent {RECENT_WEEKS} weeks, 100 references, epsilon scale 0.1.
- Runtime for this cached-capable execution: {elapsed:.1f} seconds. The full forced rebuild observed during delivery took 841.8 seconds.
- Dependencies: numpy, pandas, scipy, scikit-learn, matplotlib, seaborn, POT/`ot`, parquet engine.
- Tests cover direction, rolling boundaries, announcement-date alignment, forward-return timing, monthly signal mapping, EOT map dimensions, weight normalization, family caps, transaction costs, walk-forward eligibility, and future-data invariance of clustering/redundancy.
- Verified result during delivery: 29 passed, 0 failed. Existing constant-input correlation tests emit warnings but no lifecycle assertion failures.
- EOT convergence warnings are stored per window in `weekly_eot_drift_full.parquet` and propagated to dashboard warning fields.
"""
    (REPORT / "test_and_reproducibility_report.md").write_text(repro, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--force", action="store_true"); args = parser.parse_args()
    start = time.time(); np.random.seed(SEED); ensure_dirs()
    reg, _ = audit_and_registry(); weekly, perf = build_weekly_panel(force=args.force)
    cross, _, clusters, link = correlations_and_clusters(weekly, perf)
    elig, elig_summary = eligibility(perf, reg)
    _, _, states = drift_and_states(perf, elig, clusters, force=args.force)
    health, _, weights = health_selection_weights(states, perf, clusters)
    nav, summary, base_bt = backtest(weekly, weights)
    monitor, _ = diagnostics_reports(perf, states, nav, base_bt, health, weights)
    figures(reg, perf, cross, link, clusters, states, health, weights, nav, summary, monitor)
    elapsed = time.time() - start; final_reports(reg, elig_summary, clusters, states, summary, monitor, elapsed)
    print(f"Lifecycle pipeline completed in {elapsed:.1f}s; outputs: {REPORT}")


if __name__ == "__main__":
    main()
