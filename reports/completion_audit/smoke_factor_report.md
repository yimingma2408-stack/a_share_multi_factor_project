# Smoke Factor Report

This lightweight report uses `data/processed/clean_daily_data.csv` and the reusable modules under `src/`.
It is a local reproducibility smoke test, not the final full-universe research report.

- Daily rows: 557521
- Tickers: 234
- Date range: 2016-01-04 to 2025-12-31
- Monthly rows after factor construction: 27547

## Rank IC Summary

| factor_name | mean_rank_ic | std_rank_ic | rank_icir | rank_ic_win_rate | observations |
| --- | --- | --- | --- | --- | --- |
| liquidity_20d_z | -0.0488549 | 0.16776 | -0.291219 | 0.361345 | 119 |
| lowturn_20d_z | 0.033212 | 0.251639 | 0.131983 | 0.546218 | 119 |
| lowvol_20d_z | 0.0231729 | 0.2397 | 0.0966749 | 0.537815 | 119 |
| mom_60_20d_z | -0.0134866 | 0.177673 | -0.0759071 | 0.508621 | 116 |
| reversal_20d_z | 0.0166589 | 0.188042 | 0.0885913 | 0.474576 | 118 |

## Daily IC Decay Summary

| factor_name | horizon_days | mean_rank_ic | std_rank_ic | rank_icir | observations |
| --- | --- | --- | --- | --- | --- |
| liquidity_20d_z | 1 | -0.0196952 | 0.168144 | -0.117133 | 2420 |
| lowturn_20d_z | 1 | 0.0242746 | 0.254976 | 0.0952033 | 2420 |
| lowvol_20d_z | 1 | 0.0220978 | 0.245771 | 0.0899119 | 2419 |
| mom_60_20d_z | 1 | 0.00321955 | 0.204854 | 0.0157163 | 2369 |
| reversal_20d_z | 1 | 0.0173233 | 0.215651 | 0.0803303 | 2409 |
| liquidity_20d_z | 5 | -0.0293056 | 0.175989 | -0.16652 | 2416 |
| lowturn_20d_z | 5 | 0.0254822 | 0.250013 | 0.101923 | 2416 |
| lowvol_20d_z | 5 | 0.0173078 | 0.239164 | 0.0723681 | 2415 |
| mom_60_20d_z | 5 | -0.00482213 | 0.205141 | -0.0235064 | 2365 |
| reversal_20d_z | 5 | 0.0152256 | 0.199928 | 0.0761553 | 2405 |
| liquidity_20d_z | 10 | -0.0375449 | 0.176067 | -0.213242 | 2411 |
| lowturn_20d_z | 10 | 0.0275299 | 0.250133 | 0.110061 | 2411 |
| lowvol_20d_z | 10 | 0.0161091 | 0.23741 | 0.0678534 | 2410 |
| mom_60_20d_z | 10 | -0.00808693 | 0.199674 | -0.0405007 | 2360 |
| reversal_20d_z | 10 | 0.0116446 | 0.192187 | 0.0605901 | 2400 |
| liquidity_20d_z | 20 | -0.0511642 | 0.178882 | -0.286023 | 2401 |
| lowturn_20d_z | 20 | 0.0327323 | 0.258858 | 0.126449 | 2401 |
| lowvol_20d_z | 20 | 0.0194571 | 0.244379 | 0.0796185 | 2400 |
| mom_60_20d_z | 20 | -0.010229 | 0.18738 | -0.0545895 | 2350 |
| reversal_20d_z | 20 | 0.0167381 | 0.184018 | 0.0909594 | 2390 |
| liquidity_20d_z | 60 | -0.0824514 | 0.169411 | -0.486695 | 2361 |
| lowturn_20d_z | 60 | 0.0377915 | 0.252803 | 0.14949 | 2361 |
| lowvol_20d_z | 60 | 0.0291567 | 0.236077 | 0.123505 | 2360 |
| mom_60_20d_z | 60 | -0.0037996 | 0.168374 | -0.0225665 | 2310 |
| reversal_20d_z | 60 | 0.0143918 | 0.181883 | 0.0791267 | 2350 |

## Grouped Long-Short Summary

| factor_name | mean_long_short_return | std_long_short_return | observations |
| --- | --- | --- | --- |
| liquidity_20d_z | -0.00812449 | 0.0513641 | 119 |
| lowturn_20d_z | -0.0106733 | 0.075964 | 119 |
| lowvol_20d_z | -0.0106501 | 0.0692346 | 119 |
| mom_60_20d_z | -0.000325151 | 0.053814 | 116 |
| reversal_20d_z | 0.001359 | 0.0549083 | 118 |

## Remaining Gap

This smoke test covers price/volume factors only. Value factors, neutralized factors, attribution, and strict execution still need the missing fundamental, industry, market-cap, benchmark, and execution data.