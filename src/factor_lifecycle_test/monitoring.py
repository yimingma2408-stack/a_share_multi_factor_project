from __future__ import annotations

import numpy as np
import pandas as pd


def benjamini_hochberg(p_values: pd.Series | np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    out = np.full(len(p), np.nan)
    valid = np.isfinite(p)
    pv = p[valid]
    if not len(pv):
        return out
    order = np.argsort(pv)
    ranked = pv[order]
    adjusted = np.minimum.accumulate((ranked * len(ranked) / np.arange(1, len(ranked) + 1))[::-1])[::-1]
    restored = np.empty_like(adjusted)
    restored[order] = np.clip(adjusted, 0, 1)
    out[valid] = restored
    return out


def holm_adjust(p_values: pd.Series | np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    out = np.full(len(p), np.nan)
    valid = np.isfinite(p)
    pv = p[valid]
    if not len(pv):
        return out
    order = np.argsort(pv)
    ranked = pv[order]
    adjusted = np.maximum.accumulate((len(pv) - np.arange(len(pv))) * ranked)
    restored = np.empty_like(adjusted)
    restored[order] = np.clip(adjusted, 0, 1)
    out[valid] = restored
    return out


def add_cross_factor_fdr(panel: pd.DataFrame, p_col: str = "p_value_block", level: float = 0.10) -> pd.DataFrame:
    out = panel.copy()
    out["q_value_cross_factor"] = out.groupby("date")[p_col].transform(benjamini_hochberg)
    out["reject_fdr"] = out["q_value_cross_factor"] <= level
    out["single_week_warning"] = out["reject_fdr"]
    return out


def add_persistence(panel: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for _, group in panel.sort_values("date").groupby("factor_name", sort=False):
        g = group.copy()
        g["persistent_warning"] = g["reject_fdr"].astype(int).rolling(3, min_periods=1).sum().ge(2)
        starts, durations, start, duration = [], [], pd.NaT, 0
        for date, active in zip(g["date"], g["persistent_warning"]):
            if active:
                if duration == 0:
                    start = date
                duration += 1
            else:
                start, duration = pd.NaT, 0
            starts.append(start)
            durations.append(duration)
        g["warning_start_date"], g["warning_duration"] = starts, durations
        parts.append(g)
    return pd.concat(parts, ignore_index=True) if parts else panel.copy()


def classify_lifecycle(row: pd.Series) -> tuple[str, str]:
    historical, recent = row.get("historical_icir", np.nan), row.get("recent_icir", np.nan)
    trend = row.get("quality_trend", np.nan)
    reject, persistent = bool(row.get("reject_fdr", False)), bool(row.get("persistent_warning", False))
    bad = float(row.get("total_deterioration_score", 0) or 0)
    signed = float(row.get("aggregate_signed_improvement", 0) or 0)
    if (pd.isna(historical) or historical <= 0) and (pd.isna(recent) or recent <= 0) and signed <= 0:
        return "Dormant", "historical and recent quality are weak with no recovery evidence"
    if reject and signed > 0 and trend > 0:
        return "Recovering", "significant distribution change is improvement-led and recent quality is higher"
    if persistent and reject and signed < 0 and trend < 0 and bad > 0:
        return "Decaying", "persistent FDR warning, core deterioration and declining recent quality"
    if reject or bad > 0 and signed < 0:
        return "Watch", "single/recent distribution warning or mixed deterioration without persistent decay"
    return "Healthy", "no FDR rejection or persistent warning and quality is stable"


def test_based_penalty(q_value: pd.Series, deterioration_severity: pd.Series, gamma: float = 0.5, alpha_q: float = 0.10) -> pd.Series:
    significance = (1 - pd.to_numeric(q_value, errors="coerce") / alpha_q).clip(0, 1).fillna(0)
    severity = pd.to_numeric(deterioration_severity, errors="coerce").clip(0, 1).fillna(0)
    return (1 - gamma * significance * severity).clip(0.5, 1.0)
