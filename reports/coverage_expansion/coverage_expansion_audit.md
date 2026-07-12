# Coverage Expansion Audit

- Broad panel rows/tickers: 69,016 / 627.
- Monthly dates: 120.
- PIT violations (`available_date > date`): 0.
- Coarse industry buckets: 11.
- Industry label coverage: 100.00%.
- Industry PIT-safe ratio: 0.00%.
- Float-cap used coverage: 99.99%.

## Mode interpretation

- `strict`: reported/available financial dates, PIT-safe industry, Level A/B cap only.
- `expanded`: conservative financial lag, latest coarse industry snapshot, Level A/B/C cap.
- `proxy_sensitivity`: Level C cap rows only; diagnostic, not headline allocation.

- Eligible performance rows by mode: strict=0, expanded=1186, proxy_sensitivity=236.
- Strict has no eligible rows because the available industry data is a latest snapshot (`industry_pit_safe=false`), not a dated historical industry panel.

## Acceptance checks

- Broad ticker target (500): PASS.
- PIT violations zero: PASS.
- Float-cap or proxy coverage >=95%: PASS.
- Expanded mode comparison rows: 20.

Detailed factor comparisons are in `strict_vs_expanded_comparison.csv`; proxy and latest-snapshot limitations are intentionally retained rather than hidden.