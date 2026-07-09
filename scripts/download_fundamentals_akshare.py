from __future__ import annotations

import argparse
import contextlib
import io
import time
from pathlib import Path

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/fundamentals_akshare"
PROCESSED_DIR = ROOT / "data/processed"
PANEL_PATH = PROCESSED_DIR / "hs300_dynamic_panel_20160101_20251231_baostock.parquet"


def ticker_to_em_symbol(ticker: str) -> str:
    ticker = str(ticker).zfill(6)
    if ticker.startswith(("5", "6", "9")):
        return f"SH{ticker}"
    return f"SZ{ticker}"


def ticker_to_baostock_code(ticker: str) -> str:
    ticker = str(ticker).zfill(6)
    if ticker.startswith(("5", "6", "9")):
        return f"sh.{ticker}"
    return f"sz.{ticker}"


def read_universe(limit: int | None = None, start: int = 0, batch_size: int | None = None) -> list[str]:
    panel = pd.read_parquet(PANEL_PATH, columns=["ticker"])
    tickers = sorted(panel["ticker"].astype(str).str.zfill(6).unique().tolist())
    if start:
        tickers = tickers[start:]
    if batch_size:
        tickers = tickers[:batch_size]
    if limit:
        tickers = tickers[:limit]
    return tickers


def fetch_table(func_name: str, symbol: str) -> pd.DataFrame:
    func = getattr(ak, func_name)
    with contextlib.redirect_stderr(io.StringIO()):
        return func(symbol=symbol)


def save_raw_table(ticker: str, table_name: str, df: pd.DataFrame) -> None:
    path = RAW_DIR / table_name / f"{ticker}_{table_name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def download_financial_tables(tickers: list[str], sleep: float = 0.2, force: bool = False) -> None:
    table_funcs = {
        "income": "stock_profit_sheet_by_report_em",
        "balance": "stock_balance_sheet_by_report_em",
        "cash_flow": "stock_cash_flow_sheet_by_report_em",
    }
    stats = {name: {"cached": 0, "saved": 0, "failed": 0, "empty": 0} for name in table_funcs}
    for i, ticker in enumerate(tickers, start=1):
        symbol = ticker_to_em_symbol(ticker)
        print(f"[{i}/{len(tickers)}] {ticker} {symbol}", flush=True)
        for table_name, func_name in table_funcs.items():
            path = RAW_DIR / table_name / f"{ticker}_{table_name}.parquet"
            if path.exists() and not force:
                stats[table_name]["cached"] += 1
                continue
            try:
                df = fetch_table(func_name, symbol)
                if not df.empty:
                    df = df.copy()
                    df["ticker"] = ticker
                    df["em_symbol"] = symbol
                    stats[table_name]["saved"] += 1
                else:
                    stats[table_name]["empty"] += 1
                save_raw_table(ticker, table_name, df)
            except Exception as exc:
                stats[table_name]["failed"] += 1
                print(f"  {table_name} failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(sleep)
    print("financial download summary:", flush=True)
    for table_name, table_stats in stats.items():
        print(f"  {table_name}: {table_stats}", flush=True)


def download_industry(tickers: list[str], force: bool = False) -> pd.DataFrame:
    import baostock as bs

    path = RAW_DIR / "industry" / "industry_snapshot_baostock.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_msg}")
    rows = []
    try:
        for i, ticker in enumerate(tickers, start=1):
            if i == 1 or i % 50 == 0 or i == len(tickers):
                print(f"[{i}/{len(tickers)}] industry {ticker}", flush=True)
            code = ticker_to_baostock_code(ticker)
            rs = bs.query_stock_industry(code=code)
            if rs.error_code != "0":
                print(f"[{i}/{len(tickers)}] industry failed {ticker}: {rs.error_msg}", flush=True)
                continue
            while rs.next():
                row = dict(zip(rs.fields, rs.get_row_data()))
                row["ticker"] = ticker
                rows.append(row)
            time.sleep(0.05)
    finally:
        bs.logout()
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)
    return df


def load_raw_financials(table_name: str) -> pd.DataFrame:
    files = sorted((RAW_DIR / table_name).glob(f"*_{table_name}.parquet"))
    frames = [pd.read_parquet(path) for path in files]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def first_present(df: pd.DataFrame, candidates: list[str]) -> str | None:
    return next((col for col in candidates if col in df.columns), None)


def build_fundamental_panel() -> pd.DataFrame:
    income = load_raw_financials("income")
    balance = load_raw_financials("balance")
    cash = load_raw_financials("cash_flow")
    if income.empty or balance.empty or cash.empty:
        raise RuntimeError("Missing raw income, balance, or cash-flow tables")

    keep_common = ["ticker", "REPORT_DATE", "NOTICE_DATE", "UPDATE_DATE", "SECURITY_CODE", "SECURITY_NAME_ABBR"]
    income_cols = keep_common + [
        col
        for col in [
            "TOTAL_OPERATE_INCOME",
            "OPERATE_INCOME",
            "REVENUE",
            "TOTAL_OPERATE_COST",
            "OPERATE_COST",
            "TOTAL_PROFIT",
            "NETPROFIT",
            "PARENT_NETPROFIT",
        ]
        if col in income.columns
    ]
    balance_cols = keep_common + [
        col
        for col in ["TOTAL_PARENT_EQUITY", "TOTAL_EQUITY", "TOTAL_ASSETS", "TOTAL_LIABILITIES", "SHARE_CAPITAL"]
        if col in balance.columns
    ]
    cash_cols = keep_common + [col for col in ["NETCASH_OPERATE", "NETCASH_OPERATENOTE"] if col in cash.columns]

    inc = income[income_cols].copy()
    bal = balance[balance_cols].copy()
    csh = cash[cash_cols].copy()
    for frame in [inc, bal, csh]:
        frame["report_date"] = pd.to_datetime(frame["REPORT_DATE"], errors="coerce")
        frame["announcement_date"] = pd.to_datetime(frame["NOTICE_DATE"], errors="coerce")
        frame["ticker"] = frame["ticker"].astype(str).str.zfill(6)

    merged = inc.merge(
        bal.drop(columns=["REPORT_DATE", "NOTICE_DATE", "UPDATE_DATE", "SECURITY_CODE", "SECURITY_NAME_ABBR"], errors="ignore"),
        on=["ticker", "report_date", "announcement_date"],
        how="outer",
    ).merge(
        csh.drop(columns=["REPORT_DATE", "NOTICE_DATE", "UPDATE_DATE", "SECURITY_CODE", "SECURITY_NAME_ABBR"], errors="ignore"),
        on=["ticker", "report_date", "announcement_date"],
        how="outer",
    )

    revenue_col = first_present(merged, ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "REVENUE"])
    operating_cost_col = first_present(merged, ["TOTAL_OPERATE_COST", "OPERATE_COST"])
    net_profit_col = first_present(merged, ["PARENT_NETPROFIT", "NETPROFIT", "TOTAL_PROFIT"])
    equity_col = first_present(merged, ["TOTAL_PARENT_EQUITY", "TOTAL_EQUITY"])
    total_assets_col = first_present(merged, ["TOTAL_ASSETS"])
    cfo_col = first_present(merged, ["NETCASH_OPERATE", "NETCASH_OPERATENOTE"])
    share_col = first_present(merged, ["SHARE_CAPITAL"])

    revenue = pd.to_numeric(merged[revenue_col], errors="coerce") if revenue_col else pd.NA
    operating_cost = pd.to_numeric(merged[operating_cost_col], errors="coerce") if operating_cost_col else pd.NA
    out = pd.DataFrame(
        {
            "ticker": merged["ticker"],
            "report_date": merged["report_date"],
            "announcement_date": merged["announcement_date"],
            "revenue": revenue,
            "operating_cost": operating_cost,
            "gross_profit": revenue - operating_cost,
            "net_profit": pd.to_numeric(merged[net_profit_col], errors="coerce") if net_profit_col else pd.NA,
            "book_equity": pd.to_numeric(merged[equity_col], errors="coerce") if equity_col else pd.NA,
            "total_assets": pd.to_numeric(merged[total_assets_col], errors="coerce") if total_assets_col else pd.NA,
            "operating_cash_flow": pd.to_numeric(merged[cfo_col], errors="coerce") if cfo_col else pd.NA,
            "share_capital": pd.to_numeric(merged[share_col], errors="coerce") if share_col else pd.NA,
        }
    )
    out = out.dropna(subset=["ticker", "report_date", "announcement_date"]).drop_duplicates(
        ["ticker", "report_date", "announcement_date"], keep="last"
    )
    out = out.sort_values(["ticker", "announcement_date", "report_date"]).reset_index(drop=True)
    out.to_parquet(PROCESSED_DIR / "fundamental_statements_panel.parquet", index=False)
    return out


def build_point_in_time_panels(fundamentals: pd.DataFrame, industry: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    panel["ticker"] = panel["ticker"].astype(str).str.zfill(6)

    monthly_dates = panel.groupby(panel["date"].dt.to_period("M"))["date"].max().sort_values()
    monthly = panel[panel["date"].isin(monthly_dates.values)].copy()
    monthly = monthly.sort_values(["ticker", "date"])

    fundamentals = fundamentals.dropna(subset=["announcement_date"]).sort_values(["ticker", "announcement_date"])
    merged_parts = []
    for ticker, prices in monthly.groupby("ticker", sort=False):
        f = fundamentals[fundamentals["ticker"].eq(ticker)]
        if f.empty:
            continue
        merged = pd.merge_asof(
            prices.sort_values("date"),
            f.sort_values("announcement_date"),
            left_on="date",
            right_on="announcement_date",
            by="ticker",
            direction="backward",
        )
        merged_parts.append(merged)
    pit = pd.concat(merged_parts, ignore_index=True) if merged_parts else pd.DataFrame()
    if pit.empty:
        raise RuntimeError("No point-in-time fundamental rows were matched")

    pit["market_cap"] = pd.to_numeric(pit["raw_close"], errors="coerce") * pd.to_numeric(
        pit["share_capital"], errors="coerce"
    )
    pit["date"] = pd.to_datetime(pit["date"])
    pit = pit[
        [
            "date",
            "ticker",
            "raw_close",
            "market_cap",
            "book_equity",
            "total_assets",
            "net_profit",
            "revenue",
            "operating_cost",
            "gross_profit",
            "operating_cash_flow",
            "share_capital",
            "report_date",
            "announcement_date",
        ]
    ]
    pit.to_parquet(PROCESSED_DIR / "fundamental_panel.parquet", index=False)

    industry_out = industry.copy()
    if not industry_out.empty:
        industry_out["ticker"] = industry_out["ticker"].astype(str).str.zfill(6)
        industry_latest = industry_out.sort_values("updateDate").drop_duplicates("ticker", keep="last")
        ind_panel = monthly[["date", "ticker", "raw_close"]].merge(
            industry_latest[["ticker", "industry", "industryClassification"]],
            on="ticker",
            how="left",
        )
    else:
        ind_panel = monthly[["date", "ticker", "raw_close"]].copy()
        ind_panel["industry"] = pd.NA
        ind_panel["industryClassification"] = pd.NA
    market_cap = pit[["date", "ticker", "market_cap"]]
    ind_panel = ind_panel.merge(market_cap, on=["date", "ticker"], how="left")
    ind_panel.to_parquet(PROCESSED_DIR / "industry_size_panel.parquet", index=False)
    return pit, ind_panel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit tickers for smoke testing.")
    parser.add_argument("--start", type=int, default=0, help="Start offset in the sorted dynamic-universe ticker list.")
    parser.add_argument("--batch-size", type=int, default=None, help="Download this many tickers from --start.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--download-only", action="store_true", help="Download raw tables but do not build processed panels.")
    parser.add_argument("--build-only", action="store_true", help="Build processed panels from cached raw tables.")
    parser.add_argument("--industry-only", action="store_true", help="Refresh industry data without downloading financial tables.")
    args = parser.parse_args()

    tickers = read_universe(limit=args.limit, start=args.start, batch_size=args.batch_size)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if args.industry_only:
        industry = download_industry(tickers, force=args.force)
        print(f"industry rows: {len(industry)}, tickers: {industry['ticker'].nunique() if 'ticker' in industry else 0}", flush=True)
        return
    if not args.build_only:
        download_financial_tables(tickers, sleep=args.sleep, force=args.force)
        industry = download_industry(tickers, force=args.force)
    else:
        industry_path = RAW_DIR / "industry" / "industry_snapshot_baostock.parquet"
        industry = pd.read_parquet(industry_path) if industry_path.exists() else pd.DataFrame()
    if args.download_only:
        print("download-only mode complete", flush=True)
        return
    fundamentals = build_fundamental_panel()
    pit, ind = build_point_in_time_panels(fundamentals, industry)
    print(f"fundamental_panel rows: {len(pit)}, tickers: {pit['ticker'].nunique()}", flush=True)
    print(f"industry_size_panel rows: {len(ind)}, tickers: {ind['ticker'].nunique()}", flush=True)


if __name__ == "__main__":
    main()
