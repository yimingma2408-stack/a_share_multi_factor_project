# AKShare Financial Data Audit

## Summary

- Requested/download diagnostic tickers: 5.
- Tickers represented in the final panel: 5.
- Final panel rows: 12150.
- Final output: `data/processed/fundamental_panel_akshare.parquet`.
- Raw formats present: .parquet.
- Market-cap source: `unavailable`.
- Point-in-time violations (`available_date > date`): 0.

## Statement Download Success

| statement | successful_tickers | requested_tickers | success_rate |
| --- | --- | --- | --- |
| balance_sheet | 5 | 5 | 100.00% |
| profit_sheet | 5 | 5 | 100.00% |
| cash_flow_sheet | 5 | 5 | 100.00% |

## Target Field Mapping

| statement_type | target_field | source_column |
| --- | --- | --- |
| balance_sheet | available_date | NOTICE_DATE |
| balance_sheet | equity_parent | TOTAL_PARENT_EQUITY |
| balance_sheet | net_profit | MISSING |
| balance_sheet | net_profit_parent | MISSING |
| balance_sheet | operating_cash_flow | MISSING |
| balance_sheet | operating_cost | MISSING |
| balance_sheet | report_date | REPORT_DATE |
| balance_sheet | revenue | MISSING |
| balance_sheet | total_assets | TOTAL_ASSETS |
| balance_sheet | total_equity | TOTAL_EQUITY |
| cash_flow_sheet | available_date | NOTICE_DATE |
| cash_flow_sheet | equity_parent | MISSING |
| cash_flow_sheet | net_profit | NETPROFIT |
| cash_flow_sheet | net_profit_parent | MISSING |
| cash_flow_sheet | operating_cash_flow | NETCASH_OPERATE |
| cash_flow_sheet | operating_cost | MISSING |
| cash_flow_sheet | report_date | REPORT_DATE |
| cash_flow_sheet | revenue | MISSING |
| cash_flow_sheet | total_assets | MISSING |
| cash_flow_sheet | total_equity | MISSING |
| profit_sheet | available_date | NOTICE_DATE |
| profit_sheet | equity_parent | MISSING |
| profit_sheet | net_profit | NETPROFIT |
| profit_sheet | net_profit_parent | PARENT_NETPROFIT |
| profit_sheet | operating_cash_flow | MISSING |
| profit_sheet | operating_cost | OPERATE_COST |
| profit_sheet | report_date | REPORT_DATE |
| profit_sheet | revenue | OPERATE_INCOME, TOTAL_OPERATE_INCOME |
| profit_sheet | total_assets | MISSING |
| profit_sheet | total_equity | MISSING |

## Raw Field Lists

| statement | schema_files | unique_columns | field_summary |
| --- | --- | --- | --- |
| balance_sheet | 5 | 365 | ACCEPT_DEPOSIT, ACCEPT_DEPOSIT_INTERBANK, ACCEPT_DEPOSIT_INTERBANK_YOY, ACCEPT_DEPOSIT_YOY, ACCOUNTS_PAYABLE, ACCOUNTS_PAYABLE_YOY, ACCOUNTS_RECE, ACCOUNTS_RECE_YOY, ACCRUED_EXPENSE, ACCRUED_EXPENSE_YOY, ADVANCE_RECEIVABLES, ADVANCE_RECEIVABLES_YOY, ADVICE_ASSIGN_DIVIDEND, ADVICE_ASSIGN_DIVIDEND_YOY, AGENT_BUSINESS_ASSET, AGENT_BUSINESS_ASSET_YOY, AGENT_BUSINESS_LIAB, AGENT_BUSINESS_LIAB_YOY, AGENT_TRADE_SECURITY, AGENT_TRADE_SECURITY_YOY, AGENT_UNDERWRITE_SECURITY, AGENT_UNDERWRITE_SECURITY_YOY, AMORTIZE_COST_FINASSET, AMORTIZE_COST_FINASSET_YOY, AMORTIZE_COST_FINLIAB, AMORTIZE_COST_FINLIAB_YOY, AMORTIZE_COST_NCFINASSET, AMORTIZE_COST_NCFINASSET_YOY, AMORTIZE_COST_NCFINLIAB, AMORTIZE_COST_NCFINLIAB_YOY ... |
| profit_sheet | 5 | 222 | ABLE_OCI, ABLE_OCI_BALANCE, ABLE_OCI_BALANCE_YOY, ABLE_OCI_OTHER, ABLE_OCI_OTHER_YOY, ABLE_OCI_YOY, ACF_END_INCOME, ACF_END_INCOME_YOY, AFA_FAIRVALUE_CHANGE, AFA_FAIRVALUE_CHANGE_YOY, ASSET_DISPOSAL_INCOME, ASSET_DISPOSAL_INCOME_YOY, ASSET_IMPAIRMENT_INCOME, ASSET_IMPAIRMENT_INCOME_YOY, ASSET_IMPAIRMENT_LOSS, ASSET_IMPAIRMENT_LOSS_YOY, BASIC_EPS, BASIC_EPS_YOY, BUSINESS_MANAGE_EXPENSE, BUSINESS_MANAGE_EXPENSE_YOY, CASHFLOW_HEDGE_VALID, CASHFLOW_HEDGE_VALID_YOY, CONTINUED_NETPROFIT, CONTINUED_NETPROFIT_YOY, CONVERT_DIFF, CONVERT_DIFF_YOY, CREDITOR_FAIRVALUE_CHANGE, CREDITOR_FAIRVALUE_CHANGE_YOY, CREDITOR_IMPAIRMENT_RESERVE, CREDITOR_IMPAIRMENT_RESERVE_YOY ... |
| cash_flow_sheet | 5 | 390 | ACCEPT_INVEST_CASH, ACCEPT_INVEST_CASH_YOY, ACCOUNTS_RECE_ADD, ACCOUNTS_RECE_ADD_YOY, ACCRUED_EXPENSE_ADD, ACCRUED_EXPENSE_ADD_YOY, ADD_PLEDGE_TIMEDEPOSITS, ADD_PLEDGE_TIMEDEPOSITS_YOY, ASSET_IMPAIRMENT, ASSET_IMPAIRMENT_YOY, ASSIGN_DIVIDEND_PORFIT, ASSIGN_DIVIDEND_PORFIT_YOY, BEGIN_CASH, BEGIN_CASH_EQUIVALENTS, BEGIN_CASH_EQUIVALENTS_YOY, BEGIN_CASH_YOY, BEGIN_CCE, BEGIN_CCE_YOY, BOND_INTEREST_EXPENSE, BOND_INTEREST_EXPENSE_YOY, BORROW_FUND_ADD, BORROW_FUND_ADD_YOY, BORROW_FUND_REDUCE, BORROW_FUND_REDUCE_YOY, BORROW_REPO_ADD, BORROW_REPO_ADD_YOY, BORROW_REPO_REDUCE, BORROW_REPO_REDUCE_YOY, BUY_FIN_LEASE, BUY_FIN_LEASE_YOY ... |

## Core Field Missing Rates

| field | missing_rate |
| --- | --- |
| revenue_ttm | 0.35% |
| operating_cost_ttm | 20.00% |
| gross_profit_ttm | 20.00% |
| net_profit_ttm | 0.35% |
| net_profit_parent_ttm | 0.35% |
| operating_cash_flow_ttm | 0.35% |
| total_assets | 0.00% |
| total_equity | 0.00% |
| equity_parent | 0.00% |
| market_cap | 100.00% |

## Annual Stock Coverage

| year | covered_tickers | panel_rows |
| --- | --- | --- |
| 2016 | 5 | 1220 |
| 2017 | 5 | 1220 |
| 2018 | 5 | 1215 |
| 2019 | 5 | 1220 |
| 2020 | 5 | 1215 |
| 2021 | 5 | 1215 |
| 2022 | 5 | 1210 |
| 2023 | 5 | 1210 |
| 2024 | 5 | 1210 |
| 2025 | 5 | 1215 |

## Factor Non-Missing Rates

| factor | non_missing_rate |
| --- | --- |
| bp | 0.00% |
| ep | 0.00% |
| sp | 0.00% |
| cfp | 0.00% |
| value_composite_raw | 0.00% |
| roe | 99.65% |
| gross_profitability | 80.00% |
| ocf_to_assets | 99.65% |
| revenue_growth | 97.21% |
| earnings_growth | 97.21% |

## Available-Date Provenance

| method | rows |
| --- | --- |
| reported | 12150 |

- `reported`: AKShare supplied an announcement/update/disclosure date for every contributing statement.
- `conservative_lag`: no real availability date was supplied; quarter-specific 45/75/45/120-day lags were used.
- `mixed`: at least one contributing statement used each method. The merged availability date is the latest contributing date.

## Point-in-Time Assessment

The trade-date panel is built with a backward as-of merge and therefore only uses rows where `available_date <= date`. Financial flows are treated as cumulative year-to-date values, converted to single quarters, and only then rolled over four consecutive quarters. Missing quarters are not filled.

Residual risk remains because provider snapshots may contain later restatements without revision history. The code never substitutes report date for availability date, but a snapshot API cannot reconstruct every historical version of a restated statement.

## Failed Tickers (sample)

_No rows._

## Next Steps

- Retry failed tickers incrementally; cached files are skipped by default.
- Supply a genuine point-in-time market-cap panel. Price multiplied by statement share capital is deliberately not used.
- For production, archive dated provider snapshots or obtain revision-aware fundamentals to reduce restatement risk.