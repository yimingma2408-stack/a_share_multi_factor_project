"""Point-in-time and coverage checks for fundamental/industry research inputs."""

from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass(frozen=True)
class PitCoverageAudit:
    panel_name: str
    rows: int
    tickers: int
    dates: int
    start_date: str | None
    end_date: str | None
    available_date_coverage: float
    future_available_date_violations: int
    industry_pit_safe_ratio: float
    float_cap_coverage: float
    usable_for_formal_multifactor: bool
    formal_exclusion_reason: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_point_in_time_coverage(panel: pd.DataFrame, panel_name: str) -> PitCoverageAudit:
    """Assess direct PIT and coverage evidence without inferring missing history."""
    data = panel.copy()
    if "date" not in data or "ticker" not in data:
        raise KeyError("panel requires date and ticker columns")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    available = pd.to_datetime(data["available_date"], errors="coerce") if "available_date" in data else pd.Series(pd.NaT, index=data.index)
    violations = int((available > data["date"]).fillna(False).sum())
    available_coverage = float(available.notna().mean()) if len(data) else 0.0
    industry_pit_safe = (
        pd.to_numeric(data["industry_pit_safe"], errors="coerce").fillna(False).astype(bool)
        if "industry_pit_safe" in data else pd.Series(False, index=data.index)
    )
    industry_ratio = float(industry_pit_safe.mean()) if len(data) else 0.0
    cap_column = "float_market_cap_used" if "float_market_cap_used" in data else "market_cap" if "market_cap" in data else None
    cap_coverage = float(pd.to_numeric(data[cap_column], errors="coerce").notna().mean()) if cap_column else 0.0
    reasons = []
    if violations:
        reasons.append(f"{violations} rows use an available date after the signal date")
    if industry_ratio < 0.95:
        reasons.append("dated PIT-safe industry history is unavailable")
    if available_coverage < 0.95:
        reasons.append("financial available-date coverage is below 95%")
    if cap_coverage < 0.95:
        reasons.append("market-cap/float-cap coverage is below 95%")
    return PitCoverageAudit(
        panel_name=panel_name,
        rows=int(len(data)),
        tickers=int(data["ticker"].astype(str).nunique()),
        dates=int(data["date"].nunique()),
        start_date=str(data["date"].min().date()) if data["date"].notna().any() else None,
        end_date=str(data["date"].max().date()) if data["date"].notna().any() else None,
        available_date_coverage=available_coverage,
        future_available_date_violations=violations,
        industry_pit_safe_ratio=industry_ratio,
        float_cap_coverage=cap_coverage,
        usable_for_formal_multifactor=not reasons,
        formal_exclusion_reason="; ".join(reasons) if reasons else "",
    )
