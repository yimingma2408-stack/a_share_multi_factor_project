# A-Share Multifactor Selection Research

This repository is being built toward the full scope described in
`A股多因子选股项目大纲.md`: point-in-time A-share data preparation, factor
construction, single-factor validation, multifactor weighting, portfolio
backtesting, transaction-cost analysis, attribution, robustness checks, and a
final reproducible research report.

## Current Position

The existing completed research is strongest as an HS300 price/volume factor
prototype with EOT-based factor drift monitoring:

- Dynamic HS300 daily price/volume data exists under `data/`.
- Existing scripts evaluate reversal, momentum, low-volatility, turnover, and
  liquidity-style signals.
- Reports under `reports/eot_factor_drift_feasibility/` document monthly and
  weekly EOT drift experiments.

The project is not yet a full implementation of the outline. The largest
remaining gaps are point-in-time fundamentals for value factors, industry and
market-cap data for neutralization/attribution, strict execution modeling, and
a one-command final pipeline.

## Important Paths

- `A股多因子选股项目大纲.md`: target research scope and success criteria.
- `config/config.yaml`: central project settings.
- `src/`: reusable research modules.
- `scripts/run_outline_completion_audit.py`: current completion audit.
- `reports/completion_audit/outline_completion_audit.md`: generated audit.
- `reports/eot_factor_drift_feasibility/`: existing EOT feasibility reports.

## Run The Completion Audit

```bash
python3 scripts/run_outline_completion_audit.py
```

The audit deliberately marks uncertain or missing evidence as incomplete. This
keeps the project honest while the remaining outline items are implemented.

## Run The Lightweight Pipeline

```bash
python3 scripts/run_full_research_pipeline.py
```

In the current default Python environment this runs a CSV-based smoke factor
report plus the completion audit. Full parquet reruns require a Python
environment with `pyarrow` or `fastparquet`.

## Environment Notes

The default system `python3` can read CSV files with pandas, but may not include
`pyarrow` or `fastparquet`. Use the `quant` conda environment for parquet-based
full-panel reruns:

```bash
/opt/anaconda3/bin/conda run -n quant python scripts/run_full_research_pipeline.py
```

## Next Implementation Priorities

1. Add or download point-in-time financial statement, market-cap, industry, and
   benchmark data.
2. Build neutralized value, momentum, low-volatility, and turnover factors.
3. Generate IC, grouped-return, factor-correlation, Fama-MacBeth, and decay
   outputs on the full dynamic universe.
4. Add benchmark-relative backtests with strict buyability, transaction costs,
   and attribution.
5. Create the final one-command pipeline and final research report.
