# EOT Factor Drift Feasibility - Data Inventory

## 1. Directory Structure Summary

- Project root: `/Users/yimingma/Documents/Quant/a_share_multi_factor_project`
- Python scripts: `scripts/download_hs300_baostock.py`, `scripts/download_fundamentals_akshare.py`, `scripts/download_stock_akshare.py`, `scripts/download_stocks_efinance.py`, `scripts/factors.py`, `scripts/probe_akshare_financials.py`, `scripts/probe_data_sources.py`, `scripts/run_eot_factor_drift_feasibility.py`, `scripts/run_final_factor_research_report.py`, `scripts/run_full_research_pipeline.py`, `scripts/run_outline_completion_audit.py`, `scripts/run_quality_growth_risk_factor_research.py`, `scripts/run_smoke_factor_report.py`, `scripts/run_value_neutralized_factor_research.py`, `scripts/run_weekly_eot_drift_robustness.py`, `scripts/run_weekly_eot_factor_drift.py`
- Raw root files: 305 files
- Raw market parquet files: 1254 files
- Processed files: `data/processed/.gitkeep`, `data/processed/clean_daily_data.csv`, `data/processed/eot_factor_drift_backtest_nav.parquet`, `data/processed/eot_factor_drift_backtest_nav_weekly_drift.parquet`, `data/processed/eot_factor_drift_scores.parquet`, `data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet`, `data/processed/hs300_member_sample_20160101_20251231_baostock.parquet`, `data/processed/monthly_factor_performance.parquet`, `data/processed/monthly_factor_weights.parquet`, `data/processed/monthly_factor_weights_weekly_drift.parquet`, `data/processed/weekly_drift_backtest_grid_nav.parquet`, `data/processed/weekly_drift_penalty_weight_grid.parquet`, `data/processed/weekly_drift_signals_for_monthly_rebalance.parquet`, `data/processed/weekly_eot_factor_drift_scores.parquet`, `data/processed/weekly_factor_performance.parquet`

## 2. Key Data Files

| file | rows | columns | date range | tickers | missing rate | key columns |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| `data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet` | 1396165 | 22 | 2016-01-04 to 2025-12-31 | 627 | 1.02% | date, ticker, raw_open, raw_high, raw_low, raw_close, volume, amount, turnover, pct_change_pct, trade_status, is_st, ... |
| `data/processed/hs300_member_sample_20160101_20251231_baostock.parquet` | 723256 | 22 | 2016-01-29 to 2025-12-31 | 627 | 0.89% | date, ticker, raw_open, raw_high, raw_low, raw_close, volume, amount, turnover, pct_change_pct, trade_status, is_st, ... |
| `data/processed/clean_daily_data.csv` | 200000 | 10 | 2016-01-04 to 2025-12-31 | 85 | 0.00% | date, ticker, open, high, low, close, volume, amount, pct_change, turnover |
| `data/raw/trade_calendar_20160101_20251231.parquet` | 3653 | 2 | 2016-01-01 to 2025-12-31 | NA | 0.00% | date, is_trading_day |

## 3. Main Panel Coverage

- Main panel date range: 2016-01-04 to 2025-12-31
- Unique tickers in dynamic panel: 627
- Active HS300 member count per trading day: mean 295.7, min 276, max 300
- `qfq_close`, `amount`, `turnover`, `trade_status`, `is_st`, and `is_hs300_member` are available.
- Overall missing rate in main panel: 1.02%

## 4. Currently Supported Factors

- `reversal_1m`: supported by forward-adjusted close.
- `momentum_3m`: supported by forward-adjusted close.
- `volatility_1m`: supported by daily return / forward-adjusted close.
- `turnover_1m`: supported by turnover.
- `liquidity_1m`: supported by amount.

## 5. Temporarily Unsupported Factors

- `size`: market capitalization is not present in the current files.
- Industry-neutral factors: industry classification is not present.
- Value/quality factors: financial statement fields are not present.

## 6. Feasibility for Monthly Testing and Backtest

The current data can support a minimal monthly factor test, rolling drift diagnostics, and a preliminary stock-level long-only portfolio backtest over the HS300 dynamic universe. The test does not yet support industry/size neutralization, strict limit-up buy filters, or transaction-cost modeling.

## 7. Main Data and Implementation Risks

- Dynamic universe membership can introduce survivorship/constituent timing nuances if the original constituent source is imperfect.
- No industry and market-cap fields means factor exposures are only winsorized and standardized, not neutralized.
- No strict limit-up/limit-down buyability filter is available; `trade_status` and `is_st` are used as MVP filters.
- EOT drift uses only monthly factor-performance observations; the 6-month recent window is small and noisy.
- Transaction costs are ignored in the preliminary backtest.

## 8. Reusable and New Code

- Reusable: `scripts/factors.py` contains basic return, reversal, momentum, volatility, liquidity, and turnover factor ideas.
- New for this feasibility run: `src/eot_drift.py` and `scripts/run_eot_factor_drift_feasibility.py`.
