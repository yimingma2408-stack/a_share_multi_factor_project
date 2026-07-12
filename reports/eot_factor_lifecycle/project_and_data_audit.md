# Project and Data Audit

## Project structure and reusable modules

- Daily dynamic HS300 panel: `data/processed/hs300_dynamic_panel_20160101_20251231_baostock.parquet`; 1,396,165 rows, 627 tickers, 2016-01-04 to 2025-12-31.
- Market-cap panel: 1,396,165 rows and 627 tickers; total-cap missing 0.07%, float-cap missing 19.48%.
- Point-in-time fundamental panel: 12,150 rows but only 5 tickers, so it is not suitable for the formal cross-sectional lifecycle backtest.
- Average active dynamic-universe count: 295.7 stocks.
- Reused modules: `src/eot_drift.py`, `src/factors/*`, `src/analysis/*`, and the existing weekly/monthly EOT research outputs.
- New outputs are isolated under `data/processed/eot_factor_lifecycle/` and `reports/eot_factor_lifecycle/`.

## Factor library

- 31 implemented factor definitions were identified in code.
- 10 market factors are enabled for this lifecycle run. They use only lagged/current adjusted prices, returns, turnover and amount.
- Value, quality and growth code is implemented and uses announcement-date alignment, but current five-ticker coverage is inadequate.
- Size is available as an exposure control. Industry classification is absent, so only market-cap neutralization is performed.

## Data-quality and PIT findings

- Weekly forward returns are created only after factor values are calculated and are never supplied to preprocessing.
- Dynamic HS300 membership, trade status and ST flags are dated observations. The source does not provide a perfect historical vendor snapshot or delisting reason table, so constituent-timing and survivorship risk cannot be eliminated completely.
- `qfq_close` is used for signal and return continuity. This research assumes the stored forward-adjusted series was generated without retroactively leaking unknown corporate-action information; that vendor-level assumption cannot be independently verified here.
- Financial rows satisfy `available_date <= panel date`, but source revision histories are unavailable. Financial factors remain excluded from the formal backtest.
- Limit-up filtering uses the dated daily percentage change as an approximation; intraday queue/impact is unavailable.

## Recommended scope and risks

The formal study uses the ten enabled market factors. Other market variants are watch-only or redundancy controls; fundamental factors are rejected from allocation until broad PIT coverage is collected. The main remaining risks are missing industry neutralization, approximate tradeability/costs, dynamic-index-source fidelity, total-cap rather than full float-cap neutralization, and a single-universe research design.
