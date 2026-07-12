import pandas as pd

from src.data.akshare_financials import (
    add_ttm_and_growth,
    conservative_available_date,
    merge_statements,
    normalize_statement,
    normalize_ticker,
    ticker_to_em_symbol,
)


def test_ticker_normalization_accepts_project_formats():
    formats = ["sh.600000", "600000.SH", "SH600000", "600000"]
    assert {normalize_ticker(value) for value in formats} == {"600000"}
    assert ticker_to_em_symbol("000001.SZ") == "SZ000001"
    assert ticker_to_em_symbol("bj.430047") == "BJ430047"


def test_conservative_available_date_uses_quarter_specific_lags():
    reports = pd.Series(pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]))
    available = conservative_available_date(reports)
    assert (available - reports).dt.days.tolist() == [45, 75, 45, 120]


def test_cumulative_flows_are_converted_to_ttm_before_growth():
    dates = pd.to_datetime(
        [
            "2023-03-31",
            "2023-06-30",
            "2023-09-30",
            "2023-12-31",
            "2024-03-31",
            "2024-06-30",
            "2024-09-30",
            "2024-12-31",
        ]
    )
    notice_dates = dates + pd.Timedelta(days=30)
    profit_raw = pd.DataFrame(
        {
            "REPORT_DATE": dates,
            "NOTICE_DATE": notice_dates,
            "TOTAL_OPERATE_INCOME": [10, 25, 45, 70, 12, 30, 54, 84],
            "OPERATE_COST": [6, 15, 27, 42, 7, 18, 32, 50],
            "NETPROFIT": [1, 3, 6, 10, 2, 5, 9, 14],
            "PARENT_NETPROFIT": [1, 3, 6, 10, 2, 5, 9, 14],
        }
    )
    balance_raw = pd.DataFrame(
        {
            "REPORT_DATE": dates,
            "NOTICE_DATE": notice_dates,
            "TOTAL_ASSETS": [100] * 8,
            "TOTAL_EQUITY": [50] * 8,
            "TOTAL_PARENT_EQUITY": [48] * 8,
        }
    )
    cash_raw = pd.DataFrame(
        {
            "REPORT_DATE": dates,
            "NOTICE_DATE": notice_dates,
            "NETCASH_OPERATE": [2, 5, 9, 14, 3, 7, 12, 18],
        }
    )
    profit, _ = normalize_statement(profit_raw, "600000", "profit_sheet", "2023-01-01", "2024-12-31")
    balance, _ = normalize_statement(balance_raw, "600000", "balance_sheet", "2023-01-01", "2024-12-31")
    cash, _ = normalize_statement(cash_raw, "600000", "cash_flow_sheet", "2023-01-01", "2024-12-31")
    result = add_ttm_and_growth(
        merge_statements(
            {
                "profit_sheet": profit,
                "balance_sheet": balance,
                "cash_flow_sheet": cash,
            }
        )
    )
    final = result.iloc[-1]
    assert final["revenue_ttm"] == 84
    assert round(final["revenue_growth_yoy"], 10) == 0.2
    assert round(final["earnings_growth_yoy"], 10) == 0.4
    assert (result["available_date"] >= result["report_date"]).all()
