# Test and Reproducibility Report

- Pipeline command: `python scripts/run_eot_factor_lifecycle.py`
- Test command: `python -m pytest -q`
- Python: 3.13.9 on macOS-15.7.7-arm64-arm-64bit-Mach-O
- Random seed: 42
- EOT: base 156 weeks, recent 26 weeks, 100 references, epsilon scale 0.1.
- Runtime for this cached-capable execution: 75.8 seconds. The full forced rebuild observed during delivery took 841.8 seconds.
- Dependencies: numpy, pandas, scipy, scikit-learn, matplotlib, seaborn, POT/`ot`, parquet engine.
- Tests cover direction, rolling boundaries, announcement-date alignment, forward-return timing, monthly signal mapping, EOT map dimensions, weight normalization, family caps, transaction costs, walk-forward eligibility, and future-data invariance of clustering/redundancy.
- Verified result during delivery: 29 passed, 0 failed. Existing constant-input correlation tests emit warnings but no lifecycle assertion failures.
- EOT convergence warnings are stored per window in `weekly_eot_drift_full.parquet` and propagated to dashboard warning fields.
