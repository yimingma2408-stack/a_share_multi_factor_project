# Legacy Distance-Based EOT Factor Lifecycle Research

> **Status:** This directory is retained as a baseline and robustness benchmark. Its unscaled EOT map distance, epsilon scale 0.1 and EWMA drift classification are not formal hypothesis-test evidence. For the authoritative bootstrap-calibrated lifecycle study, see `../eot_factor_lifecycle_test/README.md`.

This directory contains an A-share factor lifecycle study built around weekly entropic optimal-transport drift. It covers project/data auditing, a unified factor registry, PIT screening, market-cap-neutralized factor preprocessing, dynamic eligibility, redundancy clustering, weekly performance distributions, EOT drift, explicit lifecycle states, health scores, factor selection, conservative weights, monthly walk-forward backtests, cost sensitivity and regime diagnostics.

The formal study uses ten market factors in the dynamic HS300 universe. Financial factors are registered but excluded because the current PIT panel covers only five tickers. EOT is positioned primarily as monitoring, not as a standalone return forecast.

Reproduce from the project root with:

```bash
python scripts/run_eot_factor_lifecycle.py
python -m pytest -q
```

Use `--force` to rebuild cached weekly cross-sections and EOT scores. Random seed is 42. Main findings and limitations are in `eot_factor_lifecycle_final_report.md`.
