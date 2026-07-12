# Project Artifact Policy

## Version-controlled source of truth

Track source code, tests, configuration, dependency manifests, Markdown reports that state research conclusions, and compact CSV audit summaries. `src/`, `scripts/`, `tests/`, `config/`, `pyproject.toml`, `requirements*.txt`, `environment.yml`, and top-level/selected report Markdown files are source-of-truth artifacts.

## Generated research data

`data/raw/` and `data/processed/` are generated or licensed data caches and remain ignored by Git. Rebuild instructions and audit reports, rather than the binary panels themselves, establish provenance. The headline formal EOT-map outputs live under `data/processed/eot_factor_lifecycle_test/`.

## Reports and figures

Research Markdown/CSV summaries are retained for review. PNG figures are regenerated artifacts and are ignored for new files. Existing tracked figures are not deleted by this policy.

## Formal EOT-map cache policy

- Final panels: `eot_map_test_panel.parquet`, coordinate diagnostics, states, dashboard, weights and NAV are reusable final caches.
- Shards: `shard_*_panel.parquet`, `shard_*_coordinates.parquet`, and `shard_*_computation.csv` are temporary parallel-recompute caches. They are ignored and may be removed only through an explicit cleanup command.
- Full pipeline policy: `--formal-eot reuse` validates/reuses delivered final panels; `rerun` recomputes; `skip` is explicit and emits a warning.

## Safe cleanup

Use `python scripts/clean_generated_cache.py --confirm` to remove only ignored temporary formal-EOT shards. It never deletes final panels, raw data, source code, Markdown reports, or tracked files.

Use `python scripts/check_project_hygiene.py` for a read-only boundary check. It reports root-level clutter, committed caches, missing keep-files, broken README path references, and temporary EOT shards. Pass `--strict` in CI when warnings should fail the job.

## Repository layout

- `src/`: reusable library code; research logic should move here once stable.
- `scripts/`: thin entry points for download, build, audit, report, and pipeline tasks.
- `tests/`: automated unit and integration tests.
- `config/`: version-controlled runtime configuration.
- `data/raw/`: ignored vendor/source data.
- `data/processed/`: ignored derived panels and reusable computational caches.
- `reports/`: reviewable conclusions and compact report tables; generated figures remain ignored.
- `notebook/`: exploratory notebooks, not authoritative pipeline logic.
- `results/`: optional disposable exports; canonical research evidence belongs in `reports/`.
