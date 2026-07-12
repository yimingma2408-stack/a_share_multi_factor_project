# Point-in-Time and Coverage Audit

## five_ticker_akshare

- Status: `available`
- Source: `/Users/yimingma/Documents/Quant/a_share_multi_factor_project/data/processed/fundamental_panel_akshare_with_market_cap.parquet`
- Rows / tickers / dates: 12,150 / 5 / 2430
- Date range: 2016-01-04 to 2025-12-31
- Available-date coverage: 100.00%
- Future-date violations: 0
- PIT-safe industry ratio: 0.00%
- Float/market-cap coverage: 99.64%
- Formal multifactor eligibility: NO
- Exclusion reason: dated PIT-safe industry history is unavailable

## broad_coverage_expansion

- Status: `available`
- Source: `/Users/yimingma/Documents/Quant/a_share_multi_factor_project/data/processed/coverage_expansion/fundamental_panel_broad.parquet`
- Rows / tickers / dates: 69,016 / 627 / 120
- Date range: 2016-01-29 to 2025-12-31
- Available-date coverage: 99.89%
- Future-date violations: 0
- PIT-safe industry ratio: 0.00%
- Float/market-cap coverage: 99.99%
- Formal multifactor eligibility: NO
- Exclusion reason: dated PIT-safe industry history is unavailable

## Decision

Neither panel is automatically promoted into the headline formal lifecycle/backtest universe by this audit. The five-ticker panel lacks cross-sectional breadth; the broad panel has no dated PIT-safe industry history. Both remain documented research inputs until the failed eligibility condition is resolved.