# Current EOT Implementation Audit

## Scope and evidence

The audit covers `src/eot_drift.py`, `src/factor_lifecycle/`, `scripts/run_eot_factor_lifecycle.py`, the weekly/monthly performance and drift parquet files, and the existing lifecycle/backtest reports. The legacy outputs are retained as baselines; the formal test is implemented in a separate namespace.

## Answers to the required audit questions

1. **What is currently computed?** `compute_eot_drift` computes the mean squared distance between two entropic-OT barycentric maps. It is an unscaled EOT-map distance, not the Sinkhorn transport cost and not a calibrated two-sample statistic. Energy distance and MMD are retained as robustness diagnostics in the lifecycle pipeline.
2. **Common reference sample?** Yes, base and recent maps use the same reference array within a window. However, those references are resampled from the pooled, jointly standardized empirical observations, rather than independently from a fixed uniform law on the unit ball.
3. **Does the statistic contain `nm/(n+m)` scaling?** No.
4. **Is bootstrap performed?** No.
5. **Does bootstrap use centered map increments?** No bootstrap exists, so no.
6. **Is a formal p-value produced?** No.
7. **Is map difference retained?** It is computed transiently as `T_base - T_recent` inside a squared norm and is not saved. The sign therefore differs from the new convention `T_recent - T_base`, although the old scalar distance is sign-invariant.
8. **Coordinate contribution support?** No.
9. **How do lifecycle states depend on drift?** The old pipeline builds an expanding-history drift z-score, EWMA-smoothed drift and past-only drift percentile. Lifecycle rules combine historical/recent ICIR and the drift percentile, while weights use a clipped monotone distance penalty. There is no calibrated rejection, FDR or persistence rule.
10. **Reusable modules.** The weekly performance panel; the three-dimensional `(rank_ic, long_short_return, downside_return)` design; past-only rolling quality features; factor registry/family labels; weekly-to-monthly as-of mapping; normalization/family caps; backtest, turnover and transaction-cost utilities; and legacy drift outputs as robustness benchmarks.
11. **Modules that must change or be added.** Base-only robust scaling; independent unit-ball references; scaled test statistic; centered weighted multiplier bootstrap; dependence-aware block extension; p/q-values; coordinate and signed-deterioration diagnostics; test-based lifecycle rules/dashboard; significance-aware experimental weights; validation and reporting.
12. **Main gap versus a formal EOT-map test.** The legacy score is an informative distance diagnostic, but it lacks the prescribed scaling and null calibration. Consequently, a high score cannot be interpreted as a statistically calibrated rejection. Pooled scaling can also attenuate the changes being tested, and the absence of signed coordinate diagnostics prevents distinguishing improvement from deterioration.

## Data and implementation notes

- The legacy standardizer uses pooled means and standard deviations. The formal implementation must estimate median/MAD only on the base window and reuse that transform for recent observations.
- The legacy epsilon uses a median of half-squared distances with default scale 0.1. The formal rule uses median non-zero pooled squared distances and primary scale 0.2.
- The old lifecycle outputs remain under `data/processed/eot_factor_lifecycle/`; formal outputs are isolated under `data/processed/eot_factor_lifecycle_test/`.
- Weekly rolling windows overlap and weekly performance is serially dependent. IID multiplier calibration is therefore a paper-faithful benchmark; block multiplier calibration is reported as a dependence-robust exploratory extension, not as a theorem-backed result for this application.

