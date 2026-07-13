# A-Share Multifactor Selection Research

This repository covers point-in-time A-share data preparation, factor
construction, single-factor validation, multifactor weighting, portfolio
backtesting, transaction-cost analysis, attribution, robustness checks, and a
final reproducible research report. The delivered formal EOT-map extension and
its acceptance criteria are recorded in `FORMAL_EOT_RESEARCH_SPEC.md`.

## Current Position

The authoritative completed research is an HS300 price/volume factor lifecycle
study using a **formal EOT-map two-sample test**. It covers 10 market factors,
3,165 weekly factor-date tests, shared unit-ball references, base-only robust
scaling, scaled map statistics, 300-draw centered IID/block bootstrap,
coordinate diagnostics, cross-factor FDR and test-based lifecycle monitoring.
The formal result is monitoring-first: it does not demonstrate allocation alpha.

Legacy distance-based EOT drift reports remain available as baselines and
robustness benchmarks, but they are not formal hypothesis-test evidence.

The project also contains broader financial/industry coverage experiments:

- Dynamic HS300 daily price/volume data exists under `data/`.
- Existing scripts evaluate reversal, momentum, low-volatility, turnover, and
  liquidity-style signals.
- Reports under `reports/eot_factor_drift_feasibility/` document legacy monthly
  and weekly distance-based EOT experiments.
- Financial/industry panels are audited but excluded from the headline formal
  allocation universe because dated PIT-safe industry history is not available.

## Important Paths

- `FORMAL_EOT_RESEARCH_SPEC.md`: formal EOT-map research scope and acceptance criteria.
- `RESEARCH_PROJECT_OUTLINE.md`: overall multifactor research outline.
- `config/config.yaml`: central project settings.
- `src/`: reusable research modules.
- `scripts/run_outline_completion_audit.py`: current completion audit.
- `reports/completion_audit/outline_completion_audit.md`: generated audit.
- `reports/eot_factor_drift_feasibility/`: existing EOT feasibility reports.
- `reports/eot_factor_lifecycle_test/`: formal common-reference EOT-map two-sample tests, centered bootstrap calibration, coordinate diagnostics, test-based lifecycle monitoring and experimental weighting.
- `reports/data_quality/point_in_time_coverage_audit.md`: formal eligibility decision for financial, industry and cap inputs.
- `ARTIFACT_POLICY.md`: source/generated/cache boundary and safe shard cleanup policy.
- `scripts/run_demo.py`: cached-data resume demo for five core market factors and EOT lifecycle monitoring.
- `scripts/run_eot_map_lifecycle_test.py`: reproduce the formal test panel (`--bootstrap 300 --references 100` for the intended final calibration).
- `reports/demo/`: compact demo report, figures, cost sensitivity, and backtest summaries.

## Repository Layout

```text
config/       version-controlled settings
data/         ignored raw inputs and processed research caches
notebook/     exploratory work only
reports/      reviewable conclusions and compact result tables
results/      optional disposable exports
scripts/      runnable pipeline, build, audit and cleanup entry points
src/          reusable research library
tests/        automated verification
```

The boundary rules are defined in `ARTIFACT_POLICY.md`. Run the read-only
hygiene check after changing the project structure:

```bash
python scripts/check_project_hygiene.py --strict
```

The resume demo deliberately uses the dynamic market panel and excludes the experimental financial,
industry, and free-float-cap coverage-extension branch from headline backtests. Those extensions remain
documented as future work and sensitivity-analysis inputs rather than being presented as commercial-grade
point-in-time data.

## Install

The delivered dependency versions are pinned to the tested `quant` environment:

```bash
python -m pip install -r requirements.txt
```

Or create the Conda environment:

```bash
conda env create -f environment.yml
```

## Run The Current-State Audit

```bash
python scripts/run_outline_completion_audit.py
python scripts/run_pit_coverage_audit.py
```

The audit distinguishes `complete`, `conditional`, and `incomplete` evidence.
It does not treat broader fundamental inputs as headline-ready unless their PIT
industry requirement is actually satisfied.

## Run The Pipeline

```bash
python scripts/run_full_research_pipeline.py
```

The `--full` workflow includes an explicit formal EOT policy:

```bash
python scripts/run_full_research_pipeline.py --full --formal-eot reuse
```

- `reuse` validates and reuses delivered final 300-draw panels;
- `rerun` recomputes them and can take many hours;
- `skip` is explicit and prints a warning.

## Known Limits

- The block multiplier is a dependence-robust exploratory extension; synthetic
  dependent-null size remains materially oversized.
- Formal headline lifecycle results use price/volume factors only.
- Broader fundamentals have zero observed future-date violations but lack dated
  PIT-safe industry history, so they remain conditional research inputs.
- Historical results are not live-trading evidence.
