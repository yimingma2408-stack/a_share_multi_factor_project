# EOT Factor Drift Feasibility Report

## 1. Executive Summary

Judgment: **partially feasible**.

The current project has enough adjusted A-share daily price/volume data to build a minimum viable HS300 monthly factor evaluation loop, compute rolling EOT drift, and run a preliminary long-only multifactor backtest. It is not yet a complete research platform because industry, market-cap, strict limit-up/limit-down buyability, and transaction-cost data are missing.

## 2. Data Availability

- Forward-adjusted OHLC data, amount, turnover, trade status, ST flag, and dynamic HS300 membership are available.
- The main panel spans 2016-01-04 to 2025-12-31, enough for 36-month base + 6-month recent rolling drift windows.
- Industry, market capitalization, financial statement data, and strict limit-up/limit-down filtering are not available.
- `quant` conda environment was used; POT is available, `pyarrow` is missing, and `fastparquet` is used for parquet output.

## 3. Factor Construction

Constructed MVP factors: `reversal_1m`, `momentum_3m`, `volatility_1m`, `turnover_1m`, and `liquidity_1m`. All factors were winsorized and cross-sectionally standardized each rebalance month. Larger values are treated as higher expected future return. No industry or size neutralization was performed because those fields are absent.

Availability snapshot:

| factor_name   | required_fields     | available_or_not   | start_date          | end_date            |   coverage_ratio |   missing_ratio | neutralized_or_not   | notes                                                                                                                   |
|:--------------|:--------------------|:-------------------|:--------------------|:--------------------|-----------------:|----------------:|:---------------------|:------------------------------------------------------------------------------------------------------------------------|
| reversal_1m   | qfq_close           | True               | 2016-02-29 00:00:00 | 2025-12-31 00:00:00 |         0.991667 |     0.00833333  | False                | Negative past 20-trading-day return. Winsorized and z-scored; no industry/size neutralization.                          |
| momentum_3m   | qfq_close           | True               | 2016-04-29 00:00:00 | 2025-12-31 00:00:00 |         0.975    |     0.025       | False                | Past 60-trading-day return. Winsorized and z-scored; no industry/size neutralization.                                   |
| volatility_1m | return_1d/qfq_close | True               | 2016-01-29 00:00:00 | 2025-12-31 00:00:00 |         1        |     0           | False                | Negative 20-trading-day realized volatility. Winsorized and z-scored; no industry/size neutralization.                  |
| turnover_1m   | turnover            | True               | 2016-01-29 00:00:00 | 2025-12-31 00:00:00 |         0.995505 |     0.00449525  | False                | Negative 20-trading-day average turnover. Winsorized and z-scored; no industry/size neutralization.                     |
| liquidity_1m  | amount              | True               | 2016-01-29 00:00:00 | 2025-12-31 00:00:00 |         0.99961  |     0.000389728 | False                | log1p of 20-trading-day average amount; not size-neutralized. Winsorized and z-scored; no industry/size neutralization. |
| size          | market_cap          | False              | NaT                 | NaT                 |         0        |     1           | False                | Skipped because market capitalization is not available.                                                                 |

## 4. Factor Performance

Performance summary:

| factor_name   |   mean_rank_ic |   std_rank_ic |       icir |   mean_long_short_return |   std_long_short_return |   t_stat_long_short |   positive_month_ratio | worst_month         | best_month          |   missing_months |   available_months |
|:--------------|---------------:|--------------:|-----------:|-------------------------:|------------------------:|--------------------:|-----------------------:|:--------------------|:--------------------|-----------------:|-------------------:|
| liquidity_1m  |     -0.0191755 |      0.158227 | -0.12119   |               0.00312598 |               0.0451456 |            0.755343 |               0.487395 | 2021-02-26 00:00:00 | 2025-07-31 00:00:00 |                0 |                119 |
| momentum_3m   |     -0.0105055 |      0.196894 | -0.0533562 |               0.00114748 |               0.0508283 |            0.243147 |               0.525862 | 2019-01-31 00:00:00 | 2020-12-31 00:00:00 |                3 |                116 |
| reversal_1m   |      0.0160751 |      0.184331 |  0.0872081 |               0.00118629 |               0.0471587 |            0.273255 |               0.474576 | 2025-08-29 00:00:00 | 2016-02-29 00:00:00 |                1 |                118 |
| turnover_1m   |      0.0744552 |      0.228276 |  0.326163  |               0.00614989 |               0.0611128 |            1.09776  |               0.596639 | 2019-01-31 00:00:00 | 2023-12-29 00:00:00 |                0 |                119 |
| volatility_1m |      0.0590206 |      0.225284 |  0.261983  |               0.00242784 |               0.0584503 |            0.453113 |               0.554622 | 2019-01-31 00:00:00 | 2023-12-29 00:00:00 |                0 |                119 |

The strongest factors by Rank ICIR in this run were turnover_1m, volatility_1m. The weakest were liquidity_1m, momentum_3m. Monthly long-short returns are visibly noisy, which is expected for a small HS300-only universe and simple price-volume factors.

## 5. EOT Drift Diagnostics

EOT status counts: `{'ok': 381}`.

EOT drift was stable enough to compute for the MVP windows. The drift series often co-moves with mean/covariance shift baselines, so the current evidence for uniquely incremental information is suggestive rather than conclusive. The 6-month recent window is small for distribution comparison; a weekly factor-performance panel would materially increase sample size and should be the next serious version. POT emitted occasional non-fatal Sinkhorn convergence warnings during the run; production use should log transport diagnostics and tune regularization/iteration settings.

Drift summary:

| factor_name   |   mean_eot_drift |   std_eot_drift |   max_eot_drift | max_drift_month     |   mean_shift_corr |   cov_shift_corr |   available_months | notes   |
|:--------------|-----------------:|----------------:|----------------:|:--------------------|------------------:|-----------------:|-------------------:|:--------|
| liquidity_1m  |          1.63505 |        0.969447 |         5.12419 | 2025-09-30 00:00:00 |          0.902446 |         0.467312 |                 77 |         |
| momentum_3m   |          1.58262 |        0.899882 |         4.7732  | 2022-02-28 00:00:00 |          0.90953  |         0.459632 |                 74 |         |
| reversal_1m   |          1.46569 |        1.00144  |         5.91186 | 2025-09-30 00:00:00 |          0.881034 |         0.686747 |                 76 |         |
| turnover_1m   |          2.01922 |        1.54666  |         6.67219 | 2019-07-31 00:00:00 |          0.912861 |         0.550563 |                 77 |         |
| volatility_1m |          1.84577 |        1.29843  |         5.91181 | 2025-11-28 00:00:00 |          0.935252 |         0.577163 |                 77 |         |

## 6. Preliminary Backtest

Backtest summary:

| strategy                              |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   monthly_win_rate |   turnover | start_date          | end_date            | notes                                                                                       |
|:--------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|-----------:|:--------------------|:--------------------|:--------------------------------------------------------------------------------------------|
| Equal-factor multifactor              |       0.0335619 |            0.159019 | 0.284507 |      -0.347212 | 0.0966612 |           0.493506 |   0.454424 | 2019-07-31 00:00:00 | 2025-11-28 00:00:00 | Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only. |
| ICIR-weighted multifactor             |       0.0553814 |            0.170018 | 0.399408 |      -0.291746 | 0.189827  |           0.532468 |   0.457429 | 2019-07-31 00:00:00 | 2025-11-28 00:00:00 | Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only. |
| ICIR + EOT drift weighted multifactor |       0.0577227 |            0.16633  | 0.417972 |      -0.285687 | 0.202049  |           0.545455 |   0.445766 | 2019-07-31 00:00:00 | 2025-11-28 00:00:00 | Stock-level top-20% long-only backtest; no transaction costs; trade_status/ST filters only. |

- Equal-factor Sharpe: 0.285; max drawdown: -34.72%.
- ICIR Sharpe: 0.399; max drawdown: -29.17%.
- ICIR + EOT Sharpe: 0.418; max drawdown: -28.57%.
- Best Sharpe in this MVP: ICIR + EOT drift weighted multifactor.

This is a stock-level top-20% long-only test with equal-weight holdings. It ignores transaction costs and uses only `trade_status`/`is_st` filters, so the result should be interpreted as a feasibility signal, not a tradable claim.

## 7. Interpretation

Recommended interpretation: **factor failure monitoring indicator first, dynamic weighting penalty second**.

EOT drift is worth continuing mainly as a monitoring signal, while direct penalty-based weighting needs more validation before becoming a production allocation rule.

As a direct allocation penalty, EOT drift can overreact when the recent window has only six monthly observations. In this run, the EOT penalty improved Sharpe relative to plain ICIR weighting, so it should not yet be treated as a proven optimizer.

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
