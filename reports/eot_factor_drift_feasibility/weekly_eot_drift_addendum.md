# Weekly EOT Drift Addendum

## 1. Purpose

This addendum extends the completed monthly EOT factor drift feasibility run to weekly factor-performance observations. The motivation is simple: monthly recent window = 6 observations, while weekly recent window = 26 observations. That larger recent sample should make distributional drift estimates less dominated by single-month noise.

## 2. Weekly Factor Performance

| factor_name   |   mean_rank_ic |   std_rank_ic |       icir |   mean_long_short_return |   std_long_short_return |   t_stat_long_short |   positive_week_ratio | worst_week   | best_week   |   missing_weeks |   available_weeks |
|:--------------|---------------:|--------------:|-----------:|-------------------------:|------------------------:|--------------------:|----------------------:|:-------------|:------------|----------------:|------------------:|
| liquidity_1m  |     -0.0140483 |      0.171604 | -0.081865  |              0.000189278 |               0.0216482 |           0.196871  |              0.497041 | 2021-08-27   | 2020-12-31  |               0 |               507 |
| momentum_3m   |     -0.0113142 |      0.213387 | -0.0530219 |              0.000705624 |               0.0275221 |           0.572144  |              0.532129 | 2024-09-20   | 2020-12-31  |               9 |               498 |
| reversal_1m   |      0.0176102 |      0.195469 |  0.0900923 |             -0.000483018 |               0.0251907 |          -0.431319  |              0.482213 | 2024-01-26   | 2018-06-22  |               1 |               506 |
| turnover_1m   |      0.0488794 |      0.215654 |  0.226656  |              0.00139329  |               0.0270044 |           1.16175   |              0.542406 | 2024-09-20   | 2024-01-26  |               0 |               507 |
| volatility_1m |      0.0404206 |      0.220454 |  0.183352  |              5.94298e-05 |               0.027455  |           0.0487402 |              0.512821 | 2018-03-23   | 2021-02-19  |               0 |               507 |

The strongest weekly Rank ICIR factors are turnover_1m, volatility_1m. The weakest/noisiest by ICIR are liquidity_1m, momentum_3m. The ordering is broadly consistent with the monthly run: turnover and low-volatility style signals remain more promising than simple momentum/liquidity in this HS300 MVP.

## 3. Weekly EOT Drift Diagnostics

| factor_name   |   mean_eot_drift |   std_eot_drift |   max_eot_drift | max_drift_week   |   mean_shift_corr |   cov_shift_corr |   available_weeks |   notes |
|:--------------|-----------------:|----------------:|----------------:|:-----------------|------------------:|-----------------:|------------------:|--------:|
| liquidity_1m  |         0.679661 |        0.278559 |         1.75008 | 2025-09-30       |          0.644235 |         0.632964 |               325 |     nan |
| momentum_3m   |         0.614286 |        0.379157 |         1.92206 | 2021-08-13       |          0.688255 |         0.836689 |               316 |     nan |
| reversal_1m   |         0.52014  |        0.315099 |         1.62759 | 2021-06-18       |          0.767911 |         0.916569 |               324 |     nan |
| turnover_1m   |         0.601    |        0.513075 |         2.8947  | 2025-02-21       |          0.910338 |         0.598903 |               325 |     nan |
| volatility_1m |         0.59341  |        0.407536 |         2.65817 | 2025-02-21       |          0.840551 |         0.731009 |               325 |     nan |

Weekly drift generated a median 4.22x more drift observations per factor than monthly drift. The median weekly/monthly drift CV ratio is 0.976. The median change in EOT/mean-shift correlation is -0.113. POT may still emit occasional Sinkhorn convergence warnings, but the workflow completed and all weekly drift rows were written.

## 4. Monitoring Value

Conclusion: **weekly EOT drift is better suited as the primary factor failure monitoring indicator**. It is also useful as a market/factor-regime diagnostic. As a dynamic weighting penalty, it remains preliminary because penalty timing, clipping, transaction costs, and neutralized factors still need validation.

The relationship with subsequent factor returns is weak and factor-dependent:

| factor_name   |   drift_corr_future_4w |   drift_corr_future_12w |   high_drift_future_4w |   normal_future_4w |   high_drift_future_12w |   normal_future_12w |
|:--------------|-----------------------:|------------------------:|-----------------------:|-------------------:|------------------------:|--------------------:|
| liquidity_1m  |              0.0785676 |               0.159885  |             0.00283338 |       -0.000323683 |             0.00187317  |        -0.000117154 |
| momentum_3m   |             -0.0248274 |              -0.111533  |             0.00361545 |       -0.000351828 |             0.000165369 |         0.000101209 |
| reversal_1m   |              0.0145332 |              -0.110544  |             0.00105166 |       -0.00163439  |            -0.00231988  |        -0.0011829   |
| turnover_1m   |              0.0383983 |               0.062949  |             0.00135059 |        0.000161593 |             0.00206172  |         0.000113498 |
| volatility_1m |              0.017339  |               0.0667038 |            -0.00118035 |       -0.000143414 |            -9.47608e-05 |        -0.000340139 |

## 5. Optional Backtest Result

| strategy                                      |   annual_return |   annual_volatility |   sharpe |   max_drawdown |   calmar |   monthly_win_rate |   turnover | start_date   | end_date   | notes                                                                                                                   |
|:----------------------------------------------|----------------:|--------------------:|---------:|---------------:|---------:|-------------------:|-----------:|:-------------|:-----------|:------------------------------------------------------------------------------------------------------------------------|
| Equal-factor multifactor                      |       0.0349142 |            0.160032 | 0.291867 |      -0.347212 | 0.100556 |           0.5      |   0.454483 | 2019-08-30   | 2025-11-28 | Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.       |
| ICIR-weighted multifactor                     |       0.0635963 |            0.169993 | 0.445251 |      -0.291746 | 0.217985 |           0.539474 |   0.459062 | 2019-08-30   | 2025-11-28 | Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.       |
| ICIR + weekly EOT drift weighted multifactor  |       0.0725108 |            0.176292 | 0.48267  |      -0.305604 | 0.237271 |           0.539474 |   0.479293 | 2019-08-30   | 2025-11-28 | Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.       |
| ICIR + monthly EOT drift weighted multifactor |       0.0659868 |            0.166248 | 0.465121 |      -0.285687 | 0.230976 |           0.552632 |   0.445766 | 2019-08-30   | 2025-11-28 | Original monthly EOT strategy, metrics aligned to weekly-drift backtest start; turnover retained from full monthly run. |

The weekly-drift backtest keeps monthly rebalancing and uses the average of the last 4 weekly EOT z-scores as the factor penalty signal. It should be read as an incremental sanity check rather than a final trading result.

## 6. Recommendation

- Formally use weekly factor-performance panel as the main EOT monitoring input: yes.
- Retain monthly panel as a slower robustness check.
- Use weekly EOT drift as the main monitoring metric before relying on it for allocation.
- Continue dynamic weighting research, but add transaction costs and penalty clipping before drawing conclusions.
- Add industry and market-cap data for neutralized factors.
- Add strict limit-up/limit-down buyability filters and realistic transaction-cost assumptions.
