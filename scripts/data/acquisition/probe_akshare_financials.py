from __future__ import annotations

import akshare as ak


def main() -> None:
    for func_name in [
        "stock_balance_sheet_by_report_em",
        "stock_cash_flow_sheet_by_report_em",
        "stock_financial_benefit_ths",
        "stock_financial_cash_ths",
        "stock_financial_debt_ths",
        "stock_financial_analysis_indicator_em",
    ]:
        print("FUNC", func_name)
        func = getattr(ak, func_name)
        try:
            try:
                df = func(symbol="SH600519")
            except TypeError:
                df = func(symbol="600519")
            print("shape", df.shape)
            print("columns", df.columns.tolist()[:120])
            print(df.head(2).to_string())
        except Exception as exc:
            print("ERROR", type(exc).__name__, exc)


if __name__ == "__main__":
    main()
