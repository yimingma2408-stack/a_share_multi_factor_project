from __future__ import annotations

import baostock as bs


def fetch_rows(result, limit: int = 3) -> list[list[str]]:
    rows = []
    while result.next() and len(rows) < limit:
        rows.append(result.get_row_data())
    return rows


def main() -> None:
    login = bs.login()
    print("login", login.error_code, login.error_msg)
    if login.error_code != "0":
        raise SystemExit(1)
    try:
        for label, query in [
            ("industry", lambda: bs.query_stock_industry(code="sh.600519")),
            ("profit", lambda: bs.query_profit_data(code="sh.600519", year=2024, quarter=4)),
            ("balance", lambda: bs.query_balance_data(code="sh.600519", year=2024, quarter=4)),
            ("cash_flow", lambda: bs.query_cash_flow_data(code="sh.600519", year=2024, quarter=4)),
            ("dupont", lambda: bs.query_dupont_data(code="sh.600519", year=2024, quarter=4)),
        ]:
            rs = query()
            print(label, rs.error_code, rs.error_msg)
            print("fields", rs.fields)
            print("rows", fetch_rows(rs))
    finally:
        bs.logout()


if __name__ == "__main__":
    main()
