# Bootstrap Calibration Report

## Implemented calibrations

The formal statistic uses the common-reference map discrepancy scaled by `nm/(n+m)`. The IID benchmark draws independent `Exp(1)` multipliers, normalizes them within each sample and recomputes both weighted empirical EOT maps. Its null statistic is based on the **centered map increments**

\[
\sqrt{nm/(n+m)}[(T_P^*-T_P)-(T_Q^*-T_Q)],
\]

not on the uncentered distance between two bootstrap maps. The application extension assigns a shared exponential multiplier to consecutive eight-week blocks and applies the same centering. Reference points remain fixed within every observed test and all its bootstrap repetitions.

## Synthetic checks

The validation includes Gaussian, Student-t and Gaussian-mixture nulls; mean, scale and correlation alternatives; single-coordinate Rank-IC and downside deterioration; and an AR(1) dependent null. Each scenario uses 20 replications and 99 bootstrap draws. Mean and downside shifts were detected in all replications. The deliberately changed Rank-IC and downside coordinates were identified in all replications.

These remain engineering validation rather than a high-precision Monte Carlo study. Gaussian null size was 5%, Student-t 0%, and Gaussian-mixture 15%. Under the deliberately challenging AR(1) null, IID rejected 60% and the eight-week block version 40%. The block version improves on IID in this experiment but remains far above nominal size. Therefore block calibration is **not stable enough to claim theory-equivalent validity** and is described only as a “dependence-robust exploratory calibration.”

## Production panel

The delivered rolling panel uses 300 bootstrap draws for both IID and block calibration at every one of 3,165 weekly factor-date endpoints. The minimum attainable adjusted-count p-value is `1/301 ≈ 0.00332`. Computational diagnostics contain 6,330 method-specific rows and record zero Sinkhorn or bootstrap failures. The aggregate measured runtime across the four parallel shards is about 47,628 CPU-seconds. A 500-draw rerun remains an optional precision extension rather than a missing deliverable.
