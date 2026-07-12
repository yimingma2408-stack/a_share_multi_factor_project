# Weekly vs Monthly EOT Drift Comparison

## Key Answers

- Weekly EOT drift was successfully computed using 156-week base and 26-week recent windows.
- Weekly observations increased by a median factor of 4.22x relative to monthly drift observations.
- Median weekly/monthly coefficient-of-variation ratio is 0.976; lower values imply a more stable scale.
- Median lag-1 autocorrelation change is 0.259; higher autocorrelation indicates smoother drift regimes.
- Median mean-shift correlation change is -0.113; negative values mean less direct overlap with simple mean shift.
- Conclusion: **weekly drift is the better primary monitoring panel**. Monthly drift should remain as a robustness cross-check.

## Quantitative Comparison

| factor_name   |   monthly_available_observations |   monthly_drift_mean |   monthly_drift_std |   monthly_drift_cv |   monthly_drift_autocorr_1 |   monthly_mean_shift_corr |   monthly_cov_shift_corr |   weekly_available_observations |   weekly_drift_mean |   weekly_drift_std |   weekly_drift_cv |   weekly_drift_autocorr_1 |   weekly_mean_shift_corr |   weekly_cov_shift_corr |   observation_multiplier |   std_ratio_weekly_to_monthly |   cv_ratio_weekly_to_monthly |   mean_shift_corr_change |
|:--------------|---------------------------------:|---------------------:|--------------------:|-------------------:|---------------------------:|--------------------------:|-------------------------:|--------------------------------:|--------------------:|-------------------:|------------------:|--------------------------:|-------------------------:|------------------------:|-------------------------:|------------------------------:|-----------------------------:|-------------------------:|
| liquidity_1m  |                               77 |              1.63505 |            0.969447 |           0.592917 |                   0.717362 |                  0.902446 |                 0.467312 |                             325 |            0.679661 |           0.278559 |          0.409849 |                  0.920032 |                 0.644235 |                0.632964 |                  4.22078 |                      0.287338 |                     0.691242 |              -0.25821    |
| momentum_3m   |                               74 |              1.58262 |            0.899882 |           0.568602 |                   0.543867 |                  0.90953  |                 0.459632 |                             316 |            0.614286 |           0.379157 |          0.617232 |                  0.932537 |                 0.688255 |                0.836689 |                  4.27027 |                      0.42134  |                     1.08553  |              -0.221275   |
| reversal_1m   |                               76 |              1.46569 |            1.00144  |           0.683257 |                   0.73376  |                  0.881034 |                 0.686747 |                             324 |            0.52014  |           0.315099 |          0.605798 |                  0.947056 |                 0.767911 |                0.916569 |                  4.26316 |                      0.314646 |                     0.886632 |              -0.113123   |
| turnover_1m   |                               77 |              2.01922 |            1.54666  |           0.76597  |                   0.700122 |                  0.912861 |                 0.550563 |                             325 |            0.601    |           0.513075 |          0.853702 |                  0.958631 |                 0.910338 |                0.598903 |                  4.22078 |                      0.33173  |                     1.11454  |              -0.00252261 |
| volatility_1m |                               77 |              1.84577 |            1.29843  |           0.70346  |                   0.666262 |                  0.935252 |                 0.577163 |                             325 |            0.59341  |           0.407536 |          0.68677  |                  0.93861  |                 0.840551 |                0.731009 |                  4.22078 |                      0.313869 |                     0.976274 |              -0.0947011  |

## Interpretation

The weekly panel gives EOT drift far more observations and aligns better with the intended distributional-monitoring use case. It does not automatically make the signal independent from mean/covariance shift, but it reduces the small-sample concern caused by the monthly 6-observation recent window. The recommended production research path is to use weekly EOT drift as the primary factor-failure monitoring signal and retain monthly drift for slower-cycle validation.

## Subsequent Performance Diagnostic

Median cross-factor correlation between weekly drift z-score and future 4-week long-short return is 0.017; the corresponding 12-week median is 0.063. The signs are mixed across factors, so weekly drift is more convincing as a contemporaneous distribution-change alarm than as a universal predictor of future factor deterioration.

| factor_name   |   drift_corr_future_4w |   drift_corr_future_12w |   high_drift_future_4w |   normal_future_4w |   high_drift_future_12w |   normal_future_12w |
|:--------------|-----------------------:|------------------------:|-----------------------:|-------------------:|------------------------:|--------------------:|
| liquidity_1m  |              0.0785676 |               0.159885  |             0.00283338 |       -0.000323683 |             0.00187317  |        -0.000117154 |
| momentum_3m   |             -0.0248274 |              -0.111533  |             0.00361545 |       -0.000351828 |             0.000165369 |         0.000101209 |
| reversal_1m   |              0.0145332 |              -0.110544  |             0.00105166 |       -0.00163439  |            -0.00231988  |        -0.0011829   |
| turnover_1m   |              0.0383983 |               0.062949  |             0.00135059 |        0.000161593 |             0.00206172  |         0.000113498 |
| volatility_1m |              0.017339  |               0.0667038 |            -0.00118035 |       -0.000143414 |            -9.47608e-05 |        -0.000340139 |
