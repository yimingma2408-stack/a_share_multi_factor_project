# Market-Cap Factor Smoke Test

- Fundamental rows/tickers: 12150 / 5.
- Market-cap panel rows/tickers: 1396165 / 627.
- Market-cap non-missing rate: 99.64%.
- Financial PIT violations: 0.
- Market-cap PIT violations: 0.
- Non-positive market caps: 0.
- Rows with `abs(ep) > 10`: 0.

## Factor Distribution

| factor | non_missing_rate | mean | std | min | p1 | p50 | p99 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bp | 0.996379 | 0.94269 | 0.636543 | 0.0941497 | 0.142816 | 0.81361 | 2.79534 | 3.3774 |
| ep | 0.99358 | 0.0434017 | 0.131844 | -1.08039 | -0.681402 | 0.0590009 | 0.238438 | 0.276725 |
| sp | 0.99358 | 0.897719 | 0.900243 | 0.0281647 | 0.0434372 | 0.671652 | 4.79926 | 6.18334 |
| cfp | 0.99358 | 0.0829017 | 0.262312 | -1.58443 | -1.37715 | 0.0907365 | 0.864383 | 1.16978 |
| value_composite_raw | 0.995638 | 0.00298849 | 0.665223 | -1.31085 | -1.1648 | 0.148735 | 1.23712 | 1.69483 |
| roe | 0.996461 | 0.0575732 | 0.11224 | -0.338828 | -0.2923 | 0.077204 | 0.226626 | 0.227345 |
| gross_profitability | 0.8 | 0.0810823 | 0.0328425 | 0.0245683 | 0.0259415 | 0.0746043 | 0.170125 | 0.171323 |
| ocf_to_assets | 0.996461 | 0.0230649 | 0.0351321 | -0.0884027 | -0.0776677 | 0.0214709 | 0.0992676 | 0.118995 |
| revenue_growth | 0.972099 | 0.1481 | 0.277243 | -0.404524 | -0.357418 | 0.120129 | 1.1357 | 3.216 |
| earnings_growth | 0.972099 | -0.230705 | 2.06665 | -16.7878 | -12.5551 | 0.0184585 | 3.61927 | 23.4527 |

## Checks

| check | passed |
| --- | --- |
| fundamental_panel_exists | True |
| market_cap_panel_exists | True |
| market_cap_non_missing_gt_90pct | True |
| bp_non_missing_gt_70pct | True |
| ep_non_missing_gt_70pct | True |
| sp_non_missing_gt_70pct | True |
| cfp_non_missing_gt_70pct | True |
| value_composite_non_missing_gt_70pct | True |
| quality_growth_factors_remain_available | True |
| point_in_time_violations_zero | True |
| market_cap_positive | True |
| no_abs_ep_above_10 | True |

## Final Result: PASS