from __future__ import annotations

import numpy as np
import pandas as pd


def build_float_cap_proxy_panel(panel: pd.DataFrame, min_group_obs: int = 3) -> pd.DataFrame:
    """Fill missing float cap with same-date industry/size ratios and past-only fallbacks."""
    required = {"date", "ticker", "market_cap", "float_market_cap", "industry_coarse"}
    missing = required - set(panel.columns)
    if missing:
        raise KeyError(f"Missing market-cap proxy columns: {sorted(missing)}")
    out = panel.copy().sort_values(["date", "ticker"]).reset_index(drop=True)
    out["market_cap"] = pd.to_numeric(out["market_cap"], errors="coerce")
    out["float_market_cap"] = pd.to_numeric(out["float_market_cap"], errors="coerce")
    out["size_bucket"] = out.groupby("date")["market_cap"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False, duplicates="drop") + 1 if s.notna().sum() >= 5 else np.nan
    )
    out["float_ratio_observed"] = (out["float_market_cap"] / out["market_cap"]).where(
        out["market_cap"].gt(0) & out["float_market_cap"].gt(0)
    ).clip(0, 1)
    prior_group: dict[tuple[object, object], float] = {}
    prior_industry: dict[object, float] = {}
    prior_global: float | None = None
    filled = []
    grades = []
    sources = []
    estimated = []
    for date, group in out.groupby("date", sort=True):
        observed = group.dropna(subset=["float_ratio_observed"])
        same_group = observed.groupby(["industry_coarse", "size_bucket"])["float_ratio_observed"].agg(["median", "count"])
        same_ind = observed.groupby("industry_coarse")["float_ratio_observed"].agg(["median", "count"])
        same_global = float(observed["float_ratio_observed"].median()) if len(observed) >= min_group_obs else np.nan
        current = []
        for idx, row in group.iterrows():
            actual = row["float_ratio_observed"]
            if pd.notna(actual):
                current.append((idx, actual, "A", "observed_float_market_cap", False))
                continue
            key = (row["industry_coarse"], row["size_bucket"])
            value = np.nan
            source = ""
            if key in same_group.index and same_group.loc[key, "count"] >= min_group_obs:
                value, source = same_group.loc[key, "median"], "same_date_industry_size_ratio"
            elif row["industry_coarse"] in same_ind.index and same_ind.loc[row["industry_coarse"], "count"] >= min_group_obs:
                value, source = same_ind.loc[row["industry_coarse"], "median"], "same_date_industry_ratio"
            elif key in prior_group:
                value, source = prior_group[key], "prior_industry_size_ratio"
            elif row["industry_coarse"] in prior_industry:
                value, source = prior_industry[row["industry_coarse"]], "prior_industry_ratio"
            elif pd.notna(same_global):
                value, source = same_global, "same_date_global_ratio"
            elif prior_global is not None:
                value, source = prior_global, "prior_global_ratio"
            if pd.notna(value) and pd.notna(row["market_cap"]) and row["market_cap"] > 0:
                current.append((idx, value, "B", source, True))
            elif pd.notna(row["market_cap"]) and row["market_cap"] > 0:
                current.append((idx, 1.0, "C", "total_market_cap_fallback", True))
            else:
                current.append((idx, np.nan, "C", "missing_total_market_cap", True))
        for idx, ratio, grade, source, is_proxy in current:
            filled.append((idx, out.loc[idx, "market_cap"] * ratio if pd.notna(ratio) else np.nan))
            grades.append((idx, grade)); sources.append((idx, source)); estimated.append((idx, is_proxy and grade == "B"))
        if len(observed) >= min_group_obs:
            prior_global = same_global
            for industry, row in same_ind.iterrows():
                if row["count"] >= min_group_obs:
                    prior_industry[industry] = row["median"]
            for key, row in same_group.iterrows():
                if row["count"] >= min_group_obs:
                    prior_group[key] = row["median"]
    values = dict(filled); grade_map = dict(grades); source_map = dict(sources); est_map = dict(estimated)
    out["float_market_cap_used"] = out.index.map(values)
    out["market_cap_quality_grade"] = out.index.map(grade_map).fillna("C")
    out["float_market_cap_source"] = out.index.map(source_map).fillna("missing_total_market_cap")
    out["float_ratio_estimated"] = out.index.map(est_map).fillna(False).astype(bool)
    out["float_market_cap_is_proxy"] = out["market_cap_quality_grade"].ne("A")
    return out
