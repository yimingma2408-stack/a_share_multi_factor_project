# EOT-Map Tests for A-Share Factor Lifecycle Diagnostics

## Motivation

The prior project used an unscaled EOT barycentric-map distance as a useful instability score. A distance alone does not provide a calibrated rejection threshold. This extension builds a formal common-reference EOT-map two-sample statistic and centered multiplier p-values, then uses coordinate diagnostics to separate distribution change from deterioration.

## Design

- Performance vector: weekly `rank_ic`, `long_short_return`, `downside_return`.
- Windows: 156 base weeks and 26 recent weeks, using observations strictly before the monitoring date.
- Scaling: median and `1.4826 × MAD` estimated only on base, with standard-deviation/minimum-scale fallback.
- References: 100 independently sampled points from the three-dimensional unit ball, shared by base, recent and bootstrap repetitions.
- Epsilon: 0.2 times the median non-zero pooled squared distance after base scaling.
- Statistic: `nm/(n+m)` times the common-reference mean squared map difference.
- Calibration: centered IID weighted multiplier benchmark and an eight-week block-multiplier exploratory extension.
- Diagnostics: additive coordinate contributions, signed improvement, deterioration shares, post-hoc coordinate p-values, cross-factor BH-FDR and two-of-three persistence.
- Lifecycle states: Healthy, Watch, Decaying, Recovering and Dormant use quality, formal rejection, persistence and direction.
- Allocation: significance/deterioration penalties are conservative experiments; monitoring remains the primary claim.

## Main findings

The panel contains 3,165 weekly factor-date tests from 2019-08-30 to 2025-12-26, each with 300 IID and 300 block multiplier draws. `turnover_1m`, `volatility_3m` and `volatility_1m` reject most often under block calibration. Downside return is the most common dominant change and deterioration coordinate. Test-based weighting does not beat the equal-factor baseline after 10 bps in this experiment, so there is no allocation-alpha claim.

## Limitations

Weekly observations are serially dependent and rolling windows overlap. The block multiplier is an applied extension without the IID paper's theoretical guarantee. Pilot bootstrap resolution and synthetic replication count are intentionally disclosed in the calibration report. Coordinate contribution is descriptive, not causal. Results inherit estimation noise, HS300/data-vendor limitations and point-in-time concerns for financial data. Nothing here guarantees live tradability.

## Reproduction

```bash
PYTHONPATH=. conda run -n quant python scripts/run_eot_map_lifecycle_test.py --bootstrap 300 --references 100
PYTHONPATH=. conda run -n quant pytest -q tests/test_eot_map_lifecycle_test.py
```

The first command is computationally expensive. Existing files were generated with the 300-draw setting recorded in `computational_diagnostics.csv` and the panel `notes` column. Parameter robustness is reproduced with `PYTHONPATH=. conda run -n quant python scripts/run_eot_map_robustness.py`.
