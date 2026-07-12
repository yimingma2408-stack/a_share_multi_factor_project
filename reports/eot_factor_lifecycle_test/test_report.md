# Test Report

## Automated coverage

`tests/test_eot_map_lifecycle_test.py` covers:

- uniform-unit-ball reference support and deterministic shared references;
- normalized target weights and barycentric-map shape;
- `nm/(n+m)` statistic scaling;
- the project-wide sign convention `map_difference = recent - base`;
- coordinate-statistic and contribution-ratio additivity;
- base-only robust scaling;
- metric direction and signed deterioration;
- BH-FDR and the two-of-three persistence rule;
- constant-within-block multiplier structure;
- execution of centered map bootstrap statistics;
- backward weekly-to-monthly mapping/no look-ahead;
- weight normalization and penalty clipping.

Verified command:

```bash
PYTHONPATH=. conda run -n quant pytest -q tests/test_eot_map_lifecycle_test.py
```

Focused formal-module result: **11 passed**.

Broader project result at the original formal-EOT delivery was **44 passed, 0 failed**. After the subsequent data-quality, attribution, evaluation and workflow coverage was added, the current full-project result is **49 passed, 0 failed**. `scripts/audit_task_711.py` also reports `TASK_711_AUDIT_OK` after checking every named deliverable, 3,165 weekly endpoints, 300 bootstrap draws, required schemas, statistic scaling, coordinate additivity, contribution ratios and 14 figures.
