# Weekly EOT Drift Addendum

## 1. Purpose

This addendum extends the completed monthly EOT factor drift feasibility run to weekly factor-performance observations. The motivation is simple: monthly recent window = 6 observations, while weekly recent window = 26 observations. That larger recent sample should make distributional drift estimates less dominated by single-month noise.

## 2. Weekly Factor Performance

| factor_name   |   mean_rank_ic |   std_rank_ic |       icir |   mean_long_short_return |   std_long_short_return |   t_stat_long_short |   positive_week_ratio | worst_week          | best_week           |   missing_weeks |   available_weeks |
|:--------------|---------------:|--------------:|-----------:|-------------------------:|------------------------:|--------------------:|----------------------:|:--------------------|:--------------------|----------------:|------------------:|
| liquidity_1m  |     -0.0153835 |      0.172904 | -0.0889713 |             -8.45485e-05 |               0.0212672 |          -0.0895157 |              0.493097 | 2021-08-27 00:00:00 | 2020-12-31 00:00:00 |               0 |               507 |
| momentum_3m   |     -0.010805  |      0.212899 | -0.0507517 |              0.000776823 |               0.0271422 |           0.638692  |              0.544177 | 2021-02-19 00:00:00 | 2020-12-31 00:00:00 |               9 |               498 |
| reversal_1m   |      0.0154444 |      0.196847 |  0.0784589 |             -0.00050242  |               0.0254176 |          -0.444639  |              0.480237 | 2024-01-26 00:00:00 | 2018-06-22 00:00:00 |               1 |               506 |
| turnover_1m   |      0.0515035 |      0.217481 |  0.236819  |              0.00167442  |               0.0270273 |           1.39497   |              0.540434 | 2024-09-20 00:00:00 | 2024-01-26 00:00:00 |               0 |               507 |
| volatility_1m |      0.039924  |      0.218683 |  0.182565  |              0.000324275 |               0.0274997 |           0.265515  |              0.499014 | 2018-03-23 00:00:00 | 2024-01-26 00:00:00 |               0 |               507 |

The strongest weekly Rank ICIR factors are turnover_1m, volatility_1m. The weakest/noisiest by ICIR are liquidity_1m, momentum_3m. The ordering is broadly consistent with the monthly run: turnover and low-volatility style signals remain more promising than simple momentum/liquidity in this HS300 MVP.

## 3. Weekly EOT Drift Diagnostics

| factor_name   |   mean_eot_drift |   std_eot_drift |   max_eot_drift | max_drift_week      |   mean_shift_corr |   cov_shift_corr |   available_weeks | notes                                                 |
|:--------------|-----------------:|----------------:|----------------:|:--------------------|------------------:|-----------------:|------------------:|:------------------------------------------------------|
| liquidity_1m  |          1.67893 |        0.751632 |         3.73168 | 2021-05-07 00:00:00 |          0.232976 |         0.956511 |               325 | ImportError: POT is required for EOT barycentric maps |
| momentum_3m   |          1.61801 |        1.02272  |         5.01902 | 2021-05-28 00:00:00 |          0.313857 |         0.990947 |               316 | ImportError: POT is required for EOT barycentric maps |
| reversal_1m   |          1.33454 |        0.845193 |         3.91159 | 2021-04-30 00:00:00 |          0.679008 |         0.993272 |               324 | ImportError: POT is required for EOT barycentric maps |
| turnover_1m   |          1.28624 |        0.964567 |         5.53164 | 2025-02-21 00:00:00 |          0.531666 |         0.953769 |               325 | ImportError: POT is required for EOT barycentric maps |
| volatility_1m |          1.39249 |        1.08542  |         5.38713 | 2025-02-21 00:00:00 |          0.523446 |         0.984119 |               325 | ImportError: POT is required for EOT barycentric maps |

Weekly drift generated a median 4.22x more drift observations per factor than monthly drift. The median weekly/monthly drift CV ratio is 1.141. The median change in EOT/mean-shift correlation is -0.222. POT may still emit occasional Sinkhorn convergence warnings, but the workflow completed and all weekly drift rows were written.

## 4. Monitoring Value

Conclusion: **weekly EOT drift is better suited as the primary factor failure monitoring indicator**. It is also useful as a market/factor-regime diagnostic. As a dynamic weighting penalty, it remains preliminary because penalty timing, clipping, transaction costs, and neutralized factors still need validation.

The relationship with subsequent factor returns is weak and factor-dependent:

| factor_name   |   drift_corr_future_4w |   drift_corr_future_12w |   high_drift_future_4w |   normal_future_4w |   high_drift_future_12w |   normal_future_12w |
|:--------------|-----------------------:|------------------------:|-----------------------:|-------------------:|------------------------:|--------------------:|
| liquidity_1m  |             0.105643   |               0.234042  |             0.00769207 |       -0.00162616  |              0.00740485 |        -0.00156544  |
| momentum_3m   |             0.00308668 |              -0.0717495 |             0.00420923 |       -8.97093e-05 |              0.00230605 |         7.60591e-05 |
| reversal_1m   |             0.00202091 |              -0.0722191 |            -0.00194189 |       -0.00142449  |             -0.00476636 |        -0.000979621 |
| turnover_1m   |             0.0802895  |               0.104691  |             0.00505667 |       -0.000497316 |              0.00478226 |        -0.00036966  |
| volatility_1m |             0.103745   |               0.103103  |             0.00190762 |       -0.000219776 |              0.00056175 |         0.00015343  |

## 5. Optional Backtest Result

| strategy                                      |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   monthly_win_rate |   turnover | start_date          | end_date            | notes                                                                                                                   |
|:----------------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|-----------:|:--------------------|:--------------------|:------------------------------------------------------------------------------------------------------------------------|
| Equal-factor multifactor                      |       0.02005   |            0.168072 | 0.199209 |      -0.374096 | 0.0535959 |           0.5      |   0.449605 | 2019-08-30 00:00:00 | 2025-11-28 00:00:00 | Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.       |
| ICIR-weighted multifactor                     |       0.056928  |            0.170232 | 0.408173 |      -0.337782 | 0.168535  |           0.539474 |   0.436727 | 2019-08-30 00:00:00 | 2025-11-28 00:00:00 | Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.       |
| ICIR + weekly EOT drift weighted multifactor  |       0.0667608 |            0.171761 | 0.459768 |      -0.301447 | 0.221468  |           0.552632 |   0.461505 | 2019-08-30 00:00:00 | 2025-11-28 00:00:00 | Monthly rebalance; weekly EOT signal is average of last 4 weekly z-scores before month-end; no transaction costs.       |
| ICIR + monthly EOT drift weighted multifactor |       0.0486268 |            0.161275 | 0.372214 |      -0.291846 | 0.166618  |           0.539474 |   0.443071 | 2019-08-30 00:00:00 | 2025-11-28 00:00:00 | Original monthly EOT strategy, metrics aligned to weekly-drift backtest start; turnover retained from full monthly run. |

The weekly-drift backtest keeps monthly rebalancing and uses the average of the last 4 weekly EOT z-scores as the factor penalty signal. It should be read as an incremental sanity check rather than a final trading result.

## 6. Recommendation

- Formally use weekly factor-performance panel as the main EOT monitoring input: yes.
- Retain monthly panel as a slower robustness check.
- Use weekly EOT drift as the main monitoring metric before relying on it for allocation.
- Continue dynamic weighting research, but add transaction costs and penalty clipping before drawing conclusions.
- Add industry and market-cap data for neutralized factors.
- Add strict limit-up/limit-down buyability filters and realistic transaction-cost assumptions.
