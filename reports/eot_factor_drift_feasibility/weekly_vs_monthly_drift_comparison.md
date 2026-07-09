# Weekly vs Monthly EOT Drift Comparison

## Key Answers

- Weekly EOT drift was successfully computed using 156-week base and 26-week recent windows.
- Weekly observations increased by a median factor of 4.22x relative to monthly drift observations.
- Median weekly/monthly coefficient-of-variation ratio is 1.141; lower values imply a more stable scale.
- Median lag-1 autocorrelation change is 0.331; higher autocorrelation indicates smoother drift regimes.
- Median mean-shift correlation change is -0.222; negative values mean less direct overlap with simple mean shift.
- Conclusion: **weekly drift is the better primary monitoring panel**. Monthly drift should remain as a robustness cross-check.

## Quantitative Comparison

| factor_name   |   monthly_available_observations |   monthly_drift_mean |   monthly_drift_std |   monthly_drift_cv |   monthly_drift_autocorr_1 |   monthly_mean_shift_corr |   monthly_cov_shift_corr |   weekly_available_observations |   weekly_drift_mean |   weekly_drift_std |   weekly_drift_cv |   weekly_drift_autocorr_1 |   weekly_mean_shift_corr |   weekly_cov_shift_corr |   observation_multiplier |   std_ratio_weekly_to_monthly |   cv_ratio_weekly_to_monthly |   mean_shift_corr_change |
|:--------------|---------------------------------:|---------------------:|--------------------:|-------------------:|---------------------------:|--------------------------:|-------------------------:|--------------------------------:|--------------------:|-------------------:|------------------:|--------------------------:|-------------------------:|------------------------:|-------------------------:|------------------------------:|-----------------------------:|-------------------------:|
| liquidity_1m  |                               77 |              2.88209 |             1.64449 |           0.570587 |                   0.813365 |                  0.657729 |                 0.850306 |                             325 |             1.67893 |           0.751632 |          0.447685 |                  0.961273 |                 0.232976 |                0.956511 |                  4.22078 |                      0.457062 |                     0.784603 |               -0.424754  |
| momentum_3m   |                               74 |              2.57993 |             1.15898 |           0.44923  |                   0.583035 |                  0.669515 |                 0.809621 |                             316 |             1.61801 |           1.02272  |          0.632083 |                  0.954395 |                 0.313857 |                0.990947 |                  4.27027 |                      0.882426 |                     1.40704  |               -0.355657  |
| reversal_1m   |                               76 |              2.56826 |             1.42568 |           0.555117 |                   0.750091 |                  0.749834 |                 0.847734 |                             324 |             1.33454 |           0.845193 |          0.633323 |                  0.951541 |                 0.679008 |                0.993272 |                  4.26316 |                      0.592834 |                     1.14088  |               -0.0708263 |
| turnover_1m   |                               77 |              3.04514 |             2.20941 |           0.725552 |                   0.601211 |                  0.674778 |                 0.889977 |                             325 |             1.28624 |           0.964567 |          0.74991  |                  0.968422 |                 0.531666 |                0.953769 |                  4.22078 |                      0.436573 |                     1.03357  |               -0.143111  |
| volatility_1m |                               77 |              2.64817 |             1.80551 |           0.681796 |                   0.638106 |                  0.745796 |                 0.891768 |                             325 |             1.39249 |           1.08542  |          0.779479 |                  0.969604 |                 0.523446 |                0.984119 |                  4.22078 |                      0.601169 |                     1.14327  |               -0.22235   |

## Interpretation

The weekly panel gives EOT drift far more observations and aligns better with the intended distributional-monitoring use case. It does not automatically make the signal independent from mean/covariance shift, but it reduces the small-sample concern caused by the monthly 6-observation recent window. The recommended production research path is to use weekly EOT drift as the primary factor-failure monitoring signal and retain monthly drift for slower-cycle validation.

## Subsequent Performance Diagnostic

Median cross-factor correlation between weekly drift z-score and future 4-week long-short return is 0.080; the corresponding 12-week median is 0.103. The signs are mixed across factors, so weekly drift is more convincing as a contemporaneous distribution-change alarm than as a universal predictor of future factor deterioration.

| factor_name   |   drift_corr_future_4w |   drift_corr_future_12w |   high_drift_future_4w |   normal_future_4w |   high_drift_future_12w |   normal_future_12w |
|:--------------|-----------------------:|------------------------:|-----------------------:|-------------------:|------------------------:|--------------------:|
| liquidity_1m  |             0.105643   |               0.234042  |             0.00769207 |       -0.00162616  |              0.00740485 |        -0.00156544  |
| momentum_3m   |             0.00308668 |              -0.0717495 |             0.00420923 |       -8.97093e-05 |              0.00230605 |         7.60591e-05 |
| reversal_1m   |             0.00202091 |              -0.0722191 |            -0.00194189 |       -0.00142449  |             -0.00476636 |        -0.000979621 |
| turnover_1m   |             0.0802895  |               0.104691  |             0.00505667 |       -0.000497316 |              0.00478226 |        -0.00036966  |
| volatility_1m |             0.103745   |               0.103103  |             0.00190762 |       -0.000219776 |              0.00056175 |         0.00015343  |
