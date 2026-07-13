from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.factor_lifecycle.lifecycle import map_weekly_signal_to_rebalance, normalized_nonnegative_weights
from src.factor_lifecycle_test.eot_map_two_sample import (
    decompose_map_statistic_by_coordinate,
    run_eot_map_two_sample_test,
    signed_coordinate_diagnostics,
)
from src.factor_lifecycle_test.metric_registry import EOT_METRIC_NAMES, METRIC_REGISTRY, metric_directions, metric_registry_frame
from src.factor_lifecycle_test.monitoring import (
    add_cross_factor_fdr,
    add_persistence,
    benjamini_hochberg,
    classify_lifecycle,
    holm_adjust,
    test_based_penalty as make_test_based_penalty,
)
from src.factor_lifecycle_test.workflow import (
    attach_latest_monthly_weights,
    coordinate_mean_permutation_pvalues,
    month_end_signals,
    rolling_quality_features,
)

DATA = ROOT / "data/processed/eot_factor_lifecycle_test"
REPORT = ROOT / "reports/eot_factor_lifecycle_test"
FIGURES = REPORT / "figures"
SOURCE = ROOT / "data/processed/eot_factor_lifecycle/weekly_factor_performance_full.parquet"
BASE, RECENT, SEED = 156, 26, 42


def _write_parquet(frame: pd.DataFrame, name: str) -> None:
    frame.to_parquet(DATA / name, index=False)


def _quality_features(perf: pd.DataFrame) -> pd.DataFrame:
    return rolling_quality_features(perf, base_window=BASE, recent_window=RECENT)


def _coordinate_followup(base: np.ndarray, recent: np.ndarray, rng: np.random.Generator, reps: int = 199) -> np.ndarray:
    return coordinate_mean_permutation_pvalues(base, recent, rng, repetitions=reps)


def build_test_panels(perf: pd.DataFrame, n_bootstrap: int, n_reference: int, monitoring_step: int = 1) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel_rows, coordinate_rows, computation_rows = [], [], []
    directions = metric_directions(EOT_METRIC_NAMES)
    # Monthly monitoring endpoints keep the walk-forward experiment computationally reproducible.
    for factor_index, (factor, g0) in enumerate(perf.groupby("factor_name", sort=True)):
        g = g0.sort_values("date").reset_index(drop=True)
        eligible = list(range(BASE + RECENT, len(g), monitoring_step))
        if eligible and eligible[-1] != len(g) - 1:
            eligible.append(len(g) - 1)
        for i in eligible:
            raw_base = g.loc[i - BASE - RECENT:i - RECENT - 1, list(EOT_METRIC_NAMES)].to_numpy(float)
            raw_recent = g.loc[i - RECENT:i - 1, list(EOT_METRIC_NAMES)].to_numpy(float)
            if len(raw_base) < BASE or len(raw_recent) < RECENT or not np.isfinite(raw_base).all() or not np.isfinite(raw_recent).all():
                continue
            date = pd.Timestamp(g.loc[i, "date"])
            seed = SEED + factor_index * 100_000 + i
            try:
                iid = run_eot_map_two_sample_test(raw_base, raw_recent, n_reference, .2, n_bootstrap, .05, seed, "iid_multiplier")
                block = run_eot_map_two_sample_test(raw_base, raw_recent, n_reference, .2, n_bootstrap, .05, seed, "block_multiplier", 8)
            except Exception as exc:
                panel_rows.append({"date": date, "factor_name": factor, "factor_family": g.loc[i, "factor_family"], "bootstrap_status": "failed", "notes": f"{type(exc).__name__}: {exc}"})
                continue
            decomposed = decompose_map_statistic_by_coordinate(block["map_difference"], BASE, RECENT, EOT_METRIC_NAMES)
            signed = signed_coordinate_diagnostics(block["map_difference"], EOT_METRIC_NAMES, directions)
            coord_p = (_coordinate_followup(raw_base, raw_recent, np.random.default_rng(seed + 9), 99)
                       if block["reject_raw"] else np.full(len(EOT_METRIC_NAMES), np.nan))
            holm, bh = holm_adjust(coord_p), benjamini_hochberg(coord_p)
            combined = []
            for k, (drow, srow) in enumerate(zip(decomposed, signed)):
                row = {**drow, **srow, "date": date, "factor_name": factor,
                       "coordinate_raw_p_value": coord_p[k], "coordinate_holm_p_value": holm[k],
                       "coordinate_bh_q_value": bh[k], "coordinate_reject": bool(np.isfinite(holm[k]) and holm[k] <= .05)}
                coordinate_rows.append(row)
                combined.append(row)
            dominant_change = max(combined, key=lambda x: x["coordinate_contribution_ratio"])
            dominant_bad = max(combined, key=lambda x: x["deterioration_share"])
            total_bad = float(sum(x["deterioration_score"] for x in combined))
            diagnostic_weights = {x.metric_name: x.diagnostic_weight for x in METRIC_REGISTRY}
            severity = float(sum(diagnostic_weights[x["metric_name"]] * x["deterioration_share"] for x in combined))
            panel_rows.append({
                "date": date, "factor_name": factor, "factor_family": g.loc[i, "factor_family"],
                "n_base": BASE, "n_recent": RECENT, "n_reference": n_reference,
                "epsilon": block["epsilon"], "epsilon_scale": .2,
                "test_statistic": block["test_statistic"], "unscaled_map_distance": block["unscaled_map_distance"],
                "bootstrap_critical_value_iid": iid["bootstrap_critical_value"],
                "bootstrap_critical_value_block": block["bootstrap_critical_value"],
                "p_value_iid": iid["p_value"], "p_value_block": block["p_value"],
                "reject_iid": iid["reject_raw"], "reject_block": block["reject_raw"],
                "sinkhorn_status": block["sinkhorn_status"], "bootstrap_status": block["bootstrap_status"],
                "block_length": 8, "dominant_change_metric": dominant_change["metric_name"],
                "dominant_deterioration_metric": dominant_bad["metric_name"],
                "dominant_change_contribution": dominant_change["coordinate_contribution_ratio"],
                "dominant_deterioration_share": dominant_bad["deterioration_share"],
                "total_deterioration_score": total_bad,
                "deterioration_severity": severity,
                "aggregate_signed_improvement": float(sum(x["signed_improvement_score"] for x in combined)),
                "metric_center": json.dumps(block["scaling_diagnostics"]["metric_center"].tolist()),
                "metric_scale": json.dumps(block["scaling_diagnostics"]["metric_scale"].tolist()),
                "scaling_fallback": json.dumps(block["scaling_diagnostics"]["scaling_fallback"].tolist()),
                "near_zero_scale_warning": bool(np.any(block["scaling_diagnostics"]["near_zero_scale_warning"])),
                "bootstrap_dependence_warning": "block multiplier is a dependence-robust exploratory calibration",
                "notes": f"weekly monitoring endpoint; {n_bootstrap} bootstrap draws per calibration",
            })
            for result in (iid, block):
                computation_rows.append({"date": date, "factor_name": factor, "n_reference": n_reference,
                    "n_bootstrap": n_bootstrap, "bootstrap_method": result["bootstrap_method"],
                    "runtime_seconds": result["runtime_seconds"], "sinkhorn_failures": int(result["sinkhorn_status"] != "ok"),
                    "bootstrap_failures": result["bootstrap_failures"], "mean_iterations": result["mean_iterations"],
                    "max_iterations": result["max_iterations"], "notes": "cached samples and common references within each test"})
    panel = add_persistence(add_cross_factor_fdr(pd.DataFrame(panel_rows)))
    return panel, pd.DataFrame(coordinate_rows), pd.DataFrame(computation_rows)


def build_lifecycle_dashboard(perf: pd.DataFrame, panel: pd.DataFrame, coords: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    quality = _quality_features(perf)
    states = panel.merge(quality[["date", "factor_name", "historical_icir", "recent_icir", "quality_trend"]], on=["date", "factor_name"], how="left")
    classified = states.apply(classify_lifecycle, axis=1)
    states[["lifecycle_state", "lifecycle_reason"]] = pd.DataFrame(classified.tolist(), index=states.index)
    states["p_value"], states["q_value"] = states["p_value_block"], states["q_value_cross_factor"]
    state_cols = ["date", "factor_name", "historical_icir", "recent_icir", "quality_trend", "test_statistic", "p_value", "q_value", "reject_fdr", "persistent_warning", "dominant_change_metric", "dominant_deterioration_metric", "total_deterioration_score", "lifecycle_state", "lifecycle_reason"]
    coord_summary = coords.groupby(["date", "factor_name"]).apply(lambda g: "; ".join(f"{r.metric_name}:{r.improvement_or_deterioration}" for r in g.itertuples()), include_groups=False).rename("signed_improvement_summary").reset_index()
    dash = states.merge(coord_summary, on=["date", "factor_name"], how="left")
    dash["eligibility_status"] = np.where(dash["lifecycle_state"].eq("Dormant"), "excluded", "eligible")
    dash["warning_level"] = np.select([
        dash["persistent_warning"] & (dash["recent_icir"] < 0), dash["persistent_warning"], dash["reject_fdr"]
    ], ["red", "orange", "yellow"], default="green")
    dash["warning_reason"] = dash["lifecycle_reason"]
    dash["current_portfolio_weight"] = np.nan
    columns = ["date", "factor_name", "factor_family", "eligibility_status", "lifecycle_state", "historical_icir", "recent_icir", "test_statistic", "p_value_iid", "p_value_block", "q_value_cross_factor", "reject_fdr", "persistent_warning", "dominant_change_metric", "dominant_change_contribution", "dominant_deterioration_metric", "dominant_deterioration_share", "signed_improvement_summary", "warning_level", "warning_reason", "current_portfolio_weight"]
    return states[state_cols], dash[columns]


def build_weights_and_backtest(perf: pd.DataFrame, panel: pd.DataFrame, states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    old_path = ROOT / "data/processed/eot_factor_lifecycle/weekly_eot_drift_smoothed.parquet"
    old = pd.read_parquet(old_path)[["date", "factor_name", "ewma_hl8"]] if old_path.exists() else pd.DataFrame()
    signal = panel.merge(states[["date", "factor_name", "historical_icir", "lifecycle_state"]], on=["date", "factor_name"], how="left")
    if not old.empty:
        signal = pd.merge_asof(signal.sort_values("date"), old.sort_values("date"), on="date", by="factor_name", direction="backward")
    else:
        signal["ewma_hl8"] = 0.0
    # Weekly tests are mapped to the last available signal in each calendar month.
    signal = month_end_signals(signal)
    signal["significance_penalty"] = make_test_based_penalty(signal["q_value_cross_factor"], pd.Series(1., index=signal.index), .5)
    signal["signed_deterioration_penalty"] = make_test_based_penalty(signal["q_value_cross_factor"], signal["deterioration_severity"], .5)
    methods = ["equal_eligible", "icir_weighting", "old_distance_eot", "formal_significance_penalty", "formal_signed_penalty", "test_lifecycle_filter", "test_lifecycle_filter_conservative"]
    weight_rows = []
    for date, g0 in signal.groupby("date"):
        g = g0.set_index("factor_name")
        icir = g["historical_icir"].clip(lower=0).fillna(0)
        for method in methods:
            if method == "equal_eligible": raw = pd.Series(1., index=g.index)
            elif method == "icir_weighting": raw = icir
            elif method == "old_distance_eot": raw = icir * (1 / (1 + g["ewma_hl8"].clip(lower=0).fillna(0))).clip(.5, 1)
            elif method == "formal_significance_penalty": raw = icir * g["significance_penalty"]
            elif method == "formal_signed_penalty": raw = icir * g["signed_deterioration_penalty"]
            elif method == "test_lifecycle_filter": raw = icir * g["lifecycle_state"].isin(["Healthy", "Watch", "Recovering"])
            else: raw = icir * g["signed_deterioration_penalty"] * g["lifecycle_state"].map({"Healthy":1., "Watch":.8, "Recovering":.6, "Decaying":.25, "Dormant":0}).fillna(0)
            w = normalized_nonnegative_weights(raw)
            for factor, value in w.items():
                weight_rows.append({"date": date, "factor_name": factor, "weighting_method": method, "raw_weight": raw[factor], "final_weight": value,
                    "q_value": g.loc[factor, "q_value_cross_factor"], "lifecycle_state": g.loc[factor, "lifecycle_state"],
                    "significance_penalty": g.loc[factor, "significance_penalty"], "deterioration_penalty": g.loc[factor, "signed_deterioration_penalty"]})
    weights = pd.DataFrame(weight_rows)
    weekly_dates = sorted(perf.date.unique())
    rows = []
    for method, wm in weights.groupby("weighting_method"):
        prior = pd.Series(dtype=float)
        for date, wg in wm.sort_values("date").groupby("date"):
            next_dates = [x for x in weekly_dates if x > date][:4]
            future = perf[(perf.date.isin(next_dates))].pivot(index="date", columns="factor_name", values="long_short_return")
            w = wg.set_index("factor_name")["final_weight"]
            gross = float(future.reindex(columns=w.index).mean().fillna(0).dot(w)) if len(future) else np.nan
            turnover = float(w.sub(prior.reindex(w.index).fillna(0)).abs().sum() / 2) if len(prior) else 1.0
            stock_turn = float(perf[(perf.date.isin(next_dates))].groupby("factor_name")["factor_turnover"].mean().reindex(w.index).fillna(0).dot(w))
            for cost in (0, 5, 10, 20):
                net = gross - cost / 10000 * (turnover + stock_turn) if np.isfinite(gross) else np.nan
                rows.append({"date": date, "strategy": method, "cost_bps": cost, "gross_return": gross, "net_return": net, "factor_weight_turnover": turnover, "stock_turnover": stock_turn})
            prior = w
    nav = pd.DataFrame(rows).sort_values(["strategy", "cost_bps", "date"])
    nav["nav"] = nav.groupby(["strategy", "cost_bps"])["net_return"].transform(lambda x: (1 + x.fillna(0)).cumprod())
    summaries = []
    for (strategy, cost), g in nav.groupby(["strategy", "cost_bps"]):
        r = g.net_return.dropna(); curve = (1 + r).cumprod(); dd = curve / curve.cummax() - 1
        ann = 12
        ret = float(curve.iloc[-1] ** (ann / len(r)) - 1) if len(r) and curve.iloc[-1] > 0 else np.nan
        vol = float(r.std(ddof=1) * math.sqrt(ann))
        summaries.append({"strategy": strategy, "cost_bps": cost, "annual_return": ret, "annual_volatility": vol,
            "sharpe": ret / vol if vol > 0 else np.nan, "max_drawdown": float(dd.min()) if len(dd) else np.nan,
            "calmar": ret / abs(dd.min()) if len(dd) and dd.min() < 0 else np.nan,
            "mean_factor_weight_turnover": g.factor_weight_turnover.mean(), "mean_stock_turnover": g.stock_turnover.mean()})
    summary = pd.DataFrame(summaries)
    return weights, nav, summary, summary[["strategy", "cost_bps", "annual_return", "sharpe", "max_drawdown"]]


def make_figures(panel: pd.DataFrame, coords: pd.DataFrame, states: pd.DataFrame, dash: pd.DataFrame, nav: pd.DataFrame, synthetic: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid")
    def save(name: str):
        plt.tight_layout(); plt.savefig(FIGURES / name, dpi=150); plt.close()
    panel.pivot(index="date", columns="factor_name", values="test_statistic").plot(figsize=(12, 6), title="Formal EOT-map test statistic"); save("01_test_statistic_timeseries.png")
    p = panel.groupby("date")[["p_value_block", "q_value_cross_factor"]].median(); p.plot(figsize=(11, 5), title="Median raw p-value and cross-factor q-value"); save("02_p_q_timeseries.png")
    code = {"Dormant":0,"Decaying":1,"Watch":2,"Recovering":3,"Healthy":4}; x=states.assign(code=states.lifecycle_state.map(code)).pivot(index="factor_name",columns="date",values="code"); plt.figure(figsize=(13,5)); sns.heatmap(x,cmap="RdYlGn"); save("03_lifecycle_timeline.png")
    for col, name in [("coordinate_contribution_ratio","04_coordinate_contribution_heatmap.png"),("deterioration_share","05_deterioration_share_heatmap.png")]:
        x=coords.groupby(["factor_name","metric_name"])[col].mean().unstack(); plt.figure(figsize=(7,5)); sns.heatmap(x,annot=True,fmt=".2f",cmap="mako"); save(name)
    panel.pivot(index="date",columns="factor_name",values="dominant_deterioration_metric").apply(lambda c: pd.Categorical(c).codes).plot(figsize=(12,5),legend=False,title="Dominant deterioration metric codes"); save("06_dominant_deterioration_timeline.png")
    plt.scatter(panel.p_value_iid,panel.p_value_block,alpha=.5); plt.plot([0,1],[0,1],'k--'); plt.xlabel("IID p-value"); plt.ylabel("Block p-value"); save("07_iid_vs_block.png")
    legacy_path = ROOT / "data/processed/eot_factor_lifecycle/weekly_eot_drift_full.parquet"
    if legacy_path.exists():
        legacy = pd.read_parquet(legacy_path, columns=["date","factor_name","eot_drift"])
        comparison = panel.merge(legacy, on=["date","factor_name"], how="inner")
        plt.scatter(comparison.eot_drift, comparison.test_statistic, alpha=.35)
        plt.xlabel("Legacy distance-based EOT drift"); plt.ylabel("Formal scaled statistic")
    else:
        plt.scatter(panel.unscaled_map_distance,panel.test_statistic,alpha=.4)
        plt.xlabel("Unscaled map distance"); plt.ylabel("Formal scaled statistic")
    save("08_old_distance_vs_formal.png")
    dash.warning_level.value_counts().plot.bar(title="Warning dashboard"); save("09_warning_dashboard.png")
    nav.query("cost_bps==10").pivot(index="date",columns="strategy",values="nav").plot(figsize=(12,6),title="Test-based strategy NAV (10 bps)"); save("10_backtest_nav.png")
    curves=nav.query("cost_bps==10").pivot(index="date",columns="strategy",values="nav"); (curves/curves.cummax()-1).plot(figsize=(12,6),title="Drawdown (10 bps)"); save("11_drawdown.png")
    nav.groupby(["cost_bps","strategy"])["net_return"].mean().unstack().plot(figsize=(10,5),title="Transaction-cost sensitivity"); save("12_cost_sensitivity.png")
    latest=coords.sort_values("date").groupby(["factor_name","metric_name"]).tail(1); latest.pivot(index="factor_name",columns="metric_name",values="coordinate_contribution_ratio").plot.bar(stacked=True,figsize=(11,5),title="Latest map-difference coordinate contributions"); save("13_map_difference_diagnostics.png")
    if len(synthetic): synthetic.groupby("scenario")["dominant_coordinate_correct"].mean().plot.bar(title="Synthetic coordinate diagnostic accuracy"); save("14_synthetic_coordinate_diagnostic.png")


def synthetic_validation(n_bootstrap: int = 99, replications: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(SEED); rows=[]
    scenarios=["gaussian_null","student_t_null","mixture_null","mean_shift","scale_change","correlation_change","rank_ic_deterioration","downside_deterioration","ar1_null"]
    for scenario in scenarios:
        for rep in range(replications):
            n,m=80,26
            if "student" in scenario: base=rng.standard_t(5,(n,3)); recent=rng.standard_t(5,(m,3))
            elif "mixture" in scenario:
                base=rng.normal(size=(n,3))+rng.binomial(1,.3,(n,1))*2; recent=rng.normal(size=(m,3))+rng.binomial(1,.3,(m,1))*2
            else: base=rng.normal(size=(n,3)); recent=rng.normal(size=(m,3))
            expected=None
            if scenario=="mean_shift": recent+=.7
            elif scenario=="scale_change": recent*=1.8
            elif scenario=="correlation_change": recent[:,1]=.8*recent[:,0]+.4*recent[:,1]
            elif scenario=="rank_ic_deterioration": recent[:,0]-=1.; expected="rank_ic"
            elif scenario=="downside_deterioration": recent[:,2]-=1.; expected="downside_return"
            if scenario=="ar1_null":
                x=rng.normal(size=(n+m,3))
                for t in range(1,len(x)): x[t]=.6*x[t-1]+x[t]
                base,recent=x[:n],x[n:]
            for method in (["iid_multiplier","block_multiplier"] if scenario=="ar1_null" else ["iid_multiplier"]):
                result=run_eot_map_two_sample_test(base,recent,40,.2,n_bootstrap,.05,SEED+rep,method,8 if method.startswith("block") else None)
                dec=decompose_map_statistic_by_coordinate(result["map_difference"],n,m,EOT_METRIC_NAMES); dominant=max(dec,key=lambda z:z["coordinate_statistic"])["metric_name"]
                rows.append({"scenario":scenario,"replication":rep,"bootstrap_method":method,"p_value":result["p_value"],"reject":result["p_value"]<=.05,"dominant_metric":dominant,"dominant_coordinate_correct": expected is None or dominant==expected})
    return pd.DataFrame(rows)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--bootstrap",type=int,default=300)
    parser.add_argument("--references",type=int,default=100)
    parser.add_argument("--monitoring-step",type=int,default=1)
    parser.add_argument("--factors",default="")
    parser.add_argument("--panel-prefix",default="")
    parser.add_argument("--reuse-panel",action="store_true")
    args=parser.parse_args()
    DATA.mkdir(parents=True,exist_ok=True); REPORT.mkdir(parents=True,exist_ok=True); FIGURES.mkdir(parents=True,exist_ok=True)
    metric_registry_frame().to_csv(REPORT/"metric_registry.csv",index=False)
    perf=pd.read_parquet(SOURCE); perf["date"]=pd.to_datetime(perf["date"])
    if args.factors:
        requested=set(args.factors.split(",")); perf=perf[perf["factor_name"].isin(requested)].copy()
    if args.reuse_panel:
        panel=pd.read_parquet(DATA/"eot_map_test_panel.parquet")
        coords=pd.read_parquet(DATA/"eot_map_coordinate_diagnostics.parquet")
        computation=pd.read_csv(REPORT/"computational_diagnostics.csv")
        panel = add_persistence(add_cross_factor_fdr(panel.drop(columns=[c for c in ["q_value_cross_factor", "reject_fdr", "single_week_warning", "persistent_warning", "warning_start_date", "warning_duration"] if c in panel])))
        rejected = panel.set_index(["date","factor_name"])["reject_block"]
        coord_keys = pd.MultiIndex.from_frame(coords[["date","factor_name"]])
        allowed = rejected.reindex(coord_keys).fillna(False).to_numpy(bool)
        followup_columns = ["coordinate_raw_p_value","coordinate_holm_p_value","coordinate_bh_q_value"]
        coords.loc[~allowed, followup_columns] = np.nan
        coords.loc[~allowed, "coordinate_reject"] = False
    else:
        panel,coords,computation=build_test_panels(perf,args.bootstrap,args.references,args.monitoring_step)
    if args.panel_prefix:
        panel.to_parquet(DATA/f"{args.panel_prefix}_panel.parquet",index=False)
        coords.to_parquet(DATA/f"{args.panel_prefix}_coordinates.parquet",index=False)
        computation.to_csv(REPORT/f"{args.panel_prefix}_computation.csv",index=False)
        print(f"generated shard {args.panel_prefix}: {len(panel)} tests")
        return
    if "deterioration_severity" not in panel:
        diagnostic_weights = {x.metric_name: x.diagnostic_weight for x in METRIC_REGISTRY}
        severity = (coords.assign(weight=coords["metric_name"].map(diagnostic_weights), weighted=lambda x: x.weight*x.deterioration_share)
                    .groupby(["date","factor_name"], as_index=False).weighted.sum().rename(columns={"weighted":"deterioration_severity"}))
        panel = panel.merge(severity, on=["date","factor_name"], how="left")
    states,dash=build_lifecycle_dashboard(perf,panel,coords)
    weights,nav,summary,costs=build_weights_and_backtest(perf,panel,states)
    current = (weights[weights["weighting_method"].eq("test_lifecycle_filter_conservative")]
               [["date", "factor_name", "final_weight"]].rename(columns={"final_weight": "test_weight"}))
    dash = attach_latest_monthly_weights(dash.drop(columns="current_portfolio_weight"), current, weight_col="test_weight")
    dash = dash.rename(columns={"test_weight": "current_portfolio_weight"})
    dash["current_portfolio_weight"] = dash["current_portfolio_weight"].fillna(0.0)
    synthetic=synthetic_validation(min(max(args.bootstrap,19),99),20)
    _write_parquet(panel,"eot_map_test_panel.parquet"); _write_parquet(coords,"eot_map_coordinate_diagnostics.parquet")
    _write_parquet(states,"factor_lifecycle_states_test_based.parquet"); _write_parquet(dash,"factor_test_dashboard.parquet")
    _write_parquet(weights,"factor_weights_test_based.parquet"); _write_parquet(nav,"backtest_nav_test_based.parquet")
    summary.to_csv(REPORT/"backtest_summary_test_based.csv",index=False); costs.to_csv(REPORT/"transaction_cost_sensitivity_test_based.csv",index=False)
    synthetic.to_csv(REPORT/"synthetic_validation_summary.csv",index=False); computation.to_csv(REPORT/"computational_diagnostics.csv",index=False)
    make_figures(panel,coords,states,dash,nav,synthetic)
    print(f"generated {len(panel)} factor-date tests, {len(coords)} coordinate rows")

if __name__ == "__main__": main()
