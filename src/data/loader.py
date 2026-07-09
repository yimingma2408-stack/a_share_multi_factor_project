from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TableSummary:
    path: str
    exists: bool
    rows: int | None = None
    columns: int | None = None
    column_names: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    tickers: int | None = None
    missing_rate: float | None = None
    error: str | None = None


def read_table(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Read CSV or parquet with a helpful error if parquet engines are absent."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, nrows=nrows)
    if path.suffix.lower() == ".parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as exc:
            raise RuntimeError(
                "Reading parquet requires pyarrow or fastparquet in the active Python environment."
            ) from exc
    raise ValueError(f"Unsupported table format: {path}")


def summarize_table(path: str | Path, nrows: int | None = None) -> TableSummary:
    path = Path(path)
    if not path.exists():
        return TableSummary(path=str(path), exists=False)
    try:
        df = read_table(path, nrows=nrows)
    except Exception as exc:
        return TableSummary(path=str(path), exists=True, error=f"{type(exc).__name__}: {exc}")

    dates = pd.to_datetime(df["date"], errors="coerce") if "date" in df.columns else None
    return TableSummary(
        path=str(path),
        exists=True,
        rows=len(df),
        columns=len(df.columns),
        column_names=list(df.columns),
        start_date=str(dates.min().date()) if dates is not None and dates.notna().any() else None,
        end_date=str(dates.max().date()) if dates is not None and dates.notna().any() else None,
        tickers=int(df["ticker"].nunique()) if "ticker" in df.columns else None,
        missing_rate=float(df.isna().mean().mean()) if len(df.columns) else 0.0,
    )


def require_columns(df: pd.DataFrame, required: Iterable[str], context: str = "dataframe") -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{context} is missing required columns: {missing}")

