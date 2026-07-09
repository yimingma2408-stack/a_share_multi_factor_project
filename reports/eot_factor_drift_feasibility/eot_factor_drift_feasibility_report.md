# EOT Factor Drift Feasibility Report

## 1. Executive Summary

Judgment: **partially feasible**.

The current project has enough adjusted A-share daily price/volume data to build a minimum viable HS300 monthly factor evaluation loop, compute rolling EOT drift, and run a preliminary long-only multifactor backtest. It is not yet a complete research platform because industry, market-cap, strict limit-up/limit-down buyability, and transaction-cost data are missing.

## 2. Data Availability

- Forward-adjusted OHLC data, amount, turnover, trade status, ST flag, and dynamic HS300 membership are available.
- The main panel spans 2016-01-04 to 2025-12-31, enough for 36-month base + 6-month recent rolling drift windows.
- Industry, market capitalization, financial statement data, and strict limit-up/limit-down filtering are not available.
- `quant` conda environment was used; POT and parquet support are required. Output uses `fastparquet` when available and otherwise falls back to the default pandas parquet engine.

## 3. Factor Construction

Constructed MVP factors: `reversal_1m`, `momentum_3m`, `volatility_1m`, `turnover_1m`, and `liquidity_1m`. All factors were winsorized and cross-sectionally standardized each rebalance month. Larger values are treated as higher expected future return. No industry or size neutralization was performed because those fields are absent.

Availability snapshot:

| factor_name   | required_fields     | available_or_not   | start_date          | end_date            |   coverage_ratio |   missing_ratio | neutralized_or_not   | notes                                                                                                                   |
|:--------------|:--------------------|:-------------------|:--------------------|:--------------------|-----------------:|----------------:|:---------------------|:------------------------------------------------------------------------------------------------------------------------|
| reversal_1m   | qfq_close           | True               | 2016-02-29 00:00:00 | 2025-12-31 00:00:00 |         0.991667 |     0.00833333  | False                | Negative past 20-trading-day return. Winsorized and z-scored; no industry/size neutralization.                          |
| momentum_3m   | qfq_close           | True               | 2016-04-29 00:00:00 | 2025-12-31 00:00:00 |         0.975    |     0.025       | False                | Past 60-trading-day return. Winsorized and z-scored; no industry/size neutralization.                                   |
| volatility_1m | return_1d/qfq_close | True               | 2016-01-29 00:00:00 | 2025-12-31 00:00:00 |         1        |     0           | False                | Negative 20-trading-day realized volatility. Winsorized and z-scored; no industry/size neutralization.                  |
| turnover_1m   | turnover            | True               | 2016-01-29 00:00:00 | 2025-12-31 00:00:00 |         0.995342 |     0.00465754  | False                | Negative 20-trading-day average turnover. Winsorized and z-scored; no industry/size neutralization.                     |
| liquidity_1m  | amount              | True               | 2016-01-29 00:00:00 | 2025-12-31 00:00:00 |         0.999575 |     0.000424678 | False                | log1p of 20-trading-day average amount; not size-neutralized. Winsorized and z-scored; no industry/size neutralization. |
| size          | market_cap          | False              | NaT                 | NaT                 |         0        |     1           | False                | Skipped because market capitalization is not available.                                                                 |

## 4. Factor Performance

Performance summary:

| factor_name   |   mean_rank_ic |   std_rank_ic |       icir |   mean_long_short_return |   std_long_short_return |   t_stat_long_short |   positive_month_ratio | worst_month         | best_month          |   missing_months |   available_months |
|:--------------|---------------:|--------------:|-----------:|-------------------------:|------------------------:|--------------------:|-----------------------:|:--------------------|:--------------------|-----------------:|-------------------:|
| liquidity_1m  |    -0.0220564  |      0.162287 | -0.13591   |              0.00151964  |               0.0443314 |            0.37394  |               0.470588 | 2021-08-31 00:00:00 | 2025-07-31 00:00:00 |                0 |                119 |
| momentum_3m   |    -0.00999666 |      0.196796 | -0.0507972 |              0.000472634 |               0.0505273 |            0.100746 |               0.543103 | 2019-01-31 00:00:00 | 2021-06-30 00:00:00 |                3 |                116 |
| reversal_1m   |     0.0172421  |      0.184863 |  0.0932696 |              0.00165811  |               0.0471349 |            0.382131 |               0.491525 | 2025-08-29 00:00:00 | 2022-10-31 00:00:00 |                1 |                118 |
| turnover_1m   |     0.0817079  |      0.22974  |  0.355654  |              0.00837061  |               0.060372  |            1.5125   |               0.613445 | 2019-01-31 00:00:00 | 2023-12-29 00:00:00 |                0 |                119 |
| volatility_1m |     0.0614147  |      0.220134 |  0.278988  |              0.00319022  |               0.0570791 |            0.609701 |               0.571429 | 2019-01-31 00:00:00 | 2023-12-29 00:00:00 |                0 |                119 |

The strongest factors by Rank ICIR in this run were turnover_1m, volatility_1m. The weakest were liquidity_1m, momentum_3m. Monthly long-short returns are visibly noisy, which is expected for a small HS300-only universe and simple price-volume factors.

## 5. EOT Drift Diagnostics

EOT status counts: `{'fallback': 381}`.

EOT drift was stable enough to compute for the MVP windows. The drift series often co-moves with mean/covariance shift baselines, so the current evidence for uniquely incremental information is suggestive rather than conclusive. The 6-month recent window is small for distribution comparison; a weekly factor-performance panel would materially increase sample size and should be the next serious version. POT emitted occasional non-fatal Sinkhorn convergence warnings during the run; production use should log transport diagnostics and tune regularization/iteration settings.

Drift summary:

| factor_name   |   mean_eot_drift |   std_eot_drift |   max_eot_drift | max_drift_month     |   mean_shift_corr |   cov_shift_corr |   available_months | notes                                                 |
|:--------------|-----------------:|----------------:|----------------:|:--------------------|------------------:|-----------------:|-------------------:|:------------------------------------------------------|
| liquidity_1m  |          2.88209 |         1.64449 |         7.39508 | 2020-06-30 00:00:00 |          0.657729 |         0.850306 |                 77 | ImportError: POT is required for EOT barycentric maps |
| momentum_3m   |          2.57993 |         1.15898 |         5.36588 | 2021-10-29 00:00:00 |          0.669515 |         0.809621 |                 74 | ImportError: POT is required for EOT barycentric maps |
| reversal_1m   |          2.56826 |         1.42568 |         6.70358 | 2025-09-30 00:00:00 |          0.749834 |         0.847734 |                 76 | ImportError: POT is required for EOT barycentric maps |
| turnover_1m   |          3.04514 |         2.20941 |        12.979   | 2019-07-31 00:00:00 |          0.674778 |         0.889977 |                 77 | ImportError: POT is required for EOT barycentric maps |
| volatility_1m |          2.64817 |         1.80551 |         9.54767 | 2019-07-31 00:00:00 |          0.745796 |         0.891768 |                 77 | ImportError: POT is required for EOT barycentric maps |

## 6. Preliminary Backtest

Backtest summary:

| strategy                              |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   monthly_win_rate |   turnover | start_date          | end_date            | notes                                                                                       |
|:--------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|-----------:|:--------------------|:--------------------|:--------------------------------------------------------------------------------------------|
| Equal-factor multifactor              |       0.0188449 |            0.166998 | 0.192368 |      -0.374096 | 0.0503745 |           0.493506 |   0.44951  | 2019-07-31 00:00:00 | 2025-11-28 00:00:00 | Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only. |
| ICIR-weighted multifactor             |       0.0490385 |            0.170181 | 0.364044 |      -0.337782 | 0.145178  |           0.532468 |   0.43605  | 2019-07-31 00:00:00 | 2025-11-28 00:00:00 | Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only. |
| ICIR + EOT drift weighted multifactor |       0.0409058 |            0.161306 | 0.326218 |      -0.291846 | 0.140162  |           0.532468 |   0.443071 | 2019-07-31 00:00:00 | 2025-11-28 00:00:00 | Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only. |

- Equal-factor Sharpe: 0.192; max drawdown: -37.41%.
- ICIR Sharpe: 0.364; max drawdown: -33.78%.
- ICIR + EOT Sharpe: 0.326; max drawdown: -29.18%.
- Best Sharpe in this MVP: ICIR-weighted multifactor.

This is a stock-level top-20% long-only test with equal-weight holdings. It ignores transaction costs and uses only `trade_status`/`is_st` filters, so the result should be interpreted as a feasibility signal, not a tradable claim.

## 7. Interpretation

Recommended interpretation: **factor failure monitoring indicator first, dynamic weighting penalty second**.

EOT drift is worth continuing mainly as a monitoring signal, while direct penalty-based weighting needs more validation before becoming a production allocation rule.

As a direct allocation penalty, EOT drift can overreact when the recent window has only six monthly observations. In this run, the EOT penalty did not clearly improve Sharpe relative to plain ICIR weighting, so it should not yet be treated as a proven optimizer.

## 8. Limitations

- Monthly recent window has only 6 observations, making EOT noisy.
- Factor universe is small and limited to price/volume signals.
- No industry or size neutralization.
- No transaction costs, slippage, or strict buyability filters.
- No bootstrap or statistical significance testing.
- Dynamic HS300 membership quality depends on the existing data source.
- EOT drift may capture noisy performance distribution changes rather than persistent regime shifts.
- A-share style cycles can make conclusions unstable across subperiods.

## 9. Recommendation

It is worth continuing, especially as a resume-friendly research project, but the next iteration should be framed as risk monitoring and factor lifecycle diagnostics rather than a finished trading system. Recommended next steps:

1. Add industry and market-cap data, then rerun neutralized factors.
2. Build weekly factor-performance observations to make EOT windows less noisy.
3. Add transaction costs and stricter limit-up/limit-down filters.
4. Test EOT drift as a monitoring dashboard signal before using it as an allocation penalty.
5. Add bootstrap/permutation tests around drift spikes and subsequent performance deterioration.

Resume wording suggestion: `Built an A-share multifactor research prototype that monitors factor performance distribution drift using entropic optimal transport and evaluates drift-aware dynamic factor weighting on a HS300 monthly backtest.`

## Deliverables

- `reports/eot_factor_drift_feasibility/data_inventory.md`
- `reports/eot_factor_drift_feasibility/factor_availability.csv`
- `data/processed/monthly_factor_performance.parquet`
- `reports/eot_factor_drift_feasibility/factor_performance_summary.csv`
- `src/eot_drift.py`
- `data/processed/eot_factor_drift_scores.parquet`
- `reports/eot_factor_drift_feasibility/eot_drift_summary.csv`
- `data/processed/monthly_factor_weights.parquet`
- `reports/eot_factor_drift_feasibility/preliminary_backtest_summary.csv`
- `data/processed/eot_factor_drift_backtest_nav.parquet`
- `reports/eot_factor_drift_feasibility/figures/`
