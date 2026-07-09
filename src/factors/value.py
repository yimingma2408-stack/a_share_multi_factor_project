from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loader import require_columns


VALUE_INPUT_COLUMNS = [
    "ticker",
    "date",
    "market_cap",
    "book_equity",
    "net_profit",
    "revenue",
    "operating_cash_flow",
]


def build_value_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Build BP, EP, SP, and CFP factors from point-in-time fundamental data."""
    require_columns(df, VALUE_INPUT_COLUMNS, "fundamental panel")
    out = df.copy()
    market_cap = pd.to_numeric(out["market_cap"], errors="coerce")
    market_cap = market_cap.where(market_cap > 0)

    out["bp"] = pd.to_numeric(out["book_equity"], errors="coerce") / market_cap
    out["ep"] = pd.to_numeric(out["net_profit"], errors="coerce") / market_cap
    out["sp"] = pd.to_numeric(out["revenue"], errors="coerce") / market_cap
    out["cfp"] = pd.to_numeric(out["operating_cash_flow"], errors="coerce") / market_cap
    out["value_composite_raw"] = out[["bp", "ep", "sp", "cfp"]].replace([np.inf, -np.inf], np.nan).mean(axis=1)
    return out

