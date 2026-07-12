from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

COARSE_INDUSTRIES = [
    "financials", "industrials", "information_technology", "healthcare",
    "consumer_discretionary", "consumer_staples", "materials_energy",
    "utilities", "real_estate", "telecom", "other",
]


def map_industry_label(value: object) -> str:
    """Map vendor-specific labels to stable coarse industry buckets."""
    text = re.sub(r"\s+", "", str(value or "")).lower()
    if not text or text in {"nan", "none", "<na>"}:
        return "other"
    rules = {
        "financials": ["银行", "保险", "证券", "金融", "bank", "finance"],
        "healthcare": ["医药", "医疗", "health", "pharm"],
        "information_technology": ["软件", "计算机", "电子", "通信设备", "半导体", "it", "technology"],
        "consumer_staples": ["食品", "饮料", "农业", "家电", "日用", "consumerstaples"],
        "consumer_discretionary": ["汽车", "传媒", "零售", "旅游", "纺织", "家居", "consumer"],
        "materials_energy": ["有色", "钢铁", "煤炭", "石油", "化工", "材料", "能源", "采掘", "metal", "energy"],
        "utilities": ["电力", "燃气", "水务", "公用", "utilities"],
        "real_estate": ["房地产", "地产", "realestate"],
        "telecom": ["电信", "运营商", "telecom"],
        "industrials": ["机械", "设备", "建筑", "交通", "物流", "工业", "国防", "军工", "industr"],
    }
    for bucket, keywords in rules.items():
        if any(keyword.lower() in text for keyword in keywords):
            return bucket
    return "other"


def build_coarse_industry_panel(
    universe: pd.DataFrame,
    raw_industry: pd.DataFrame | None = None,
    snapshot_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build a dated coarse industry panel without claiming historical PIT safety."""
    base = universe[["date", "ticker"]].drop_duplicates().copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base["ticker"] = base["ticker"].astype(str).str.zfill(6)
    if raw_industry is None or raw_industry.empty:
        base["industry_coarse"] = "other"
        base["industry_source"] = "missing_default_other"
        base["industry_asof_date"] = pd.NaT
        base["industry_pit_safe"] = False
        return base
    raw = raw_industry.copy()
    ticker_col = next((c for c in ["ticker", "code", "股票代码"] if c in raw.columns), None)
    label_col = next((c for c in ["industry", "industryClassification", "行业", "行业分类"] if c in raw.columns), None)
    update_col = next((c for c in ["updateDate", "update_date", "date", "日期"] if c in raw.columns), None)
    if ticker_col is None or label_col is None:
        return build_coarse_industry_panel(universe, None, snapshot_date)
    raw["ticker"] = raw[ticker_col].astype(str).str.extract(r"(\d{6})", expand=False)
    raw["industry_coarse"] = raw[label_col].map(map_industry_label)
    raw["industry_asof_date"] = pd.to_datetime(raw[update_col], errors="coerce") if update_col else pd.Timestamp(snapshot_date or pd.Timestamp.today().normalize())
    raw = raw.dropna(subset=["ticker"]).sort_values("industry_asof_date").drop_duplicates("ticker", keep="last")
    out = base.merge(raw[["ticker", "industry_coarse", "industry_asof_date"]], on="ticker", how="left")
    out["industry_coarse"] = out["industry_coarse"].fillna("other")
    out["industry_source"] = np.where(out["industry_asof_date"].notna(), "latest_snapshot", "missing_default_other")
    out["industry_pit_safe"] = False
    return out


def coarse_industry_summary(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.groupby("industry_coarse", dropna=False).agg(
        tickers=("ticker", "nunique"), rows=("ticker", "size"),
        pit_safe_ratio=("industry_pit_safe", "mean"),
    ).reset_index()
