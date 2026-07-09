# Value and Neutralized Factor Research

- Universe: dynamic HS300 monthly observations
- Fundamental rows: 28286
- Fundamental tickers: 241
- Usable tickers with market cap, book equity, net profit, revenue, and cash flow: 224
- Research rows after return merge: 28286
- Date range: 2016-01-29 to 2025-12-31

## Rank IC Summary

| factor_name | mean_rank_ic | std_rank_ic | rank_icir | rank_ic_win_rate | observations |
| --- | --- | --- | --- | --- | --- |
| ep_industry_size_neutral_z | 0.036919 | 0.121106 | 0.304849 | 0.588235 | 119 |
| ep_size_neutral_z | 0.0358552 | 0.173427 | 0.206745 | 0.613445 | 119 |
| ep_industry_neutral_z | 0.0338136 | 0.111899 | 0.302179 | 0.630252 | 119 |
| cfp_z | 0.030803 | 0.120421 | 0.255795 | 0.630252 | 119 |
| ep_z | 0.0302036 | 0.168182 | 0.179589 | 0.596639 | 119 |
| cfp_size_neutral_z | 0.0253932 | 0.138035 | 0.183962 | 0.638655 | 119 |
| cfp_industry_size_neutral_z | 0.0234646 | 0.0948151 | 0.247477 | 0.605042 | 119 |
| cfp_industry_neutral_z | 0.0212696 | 0.0861629 | 0.246853 | 0.613445 | 119 |
| bp_industry_neutral_z | 0.0183633 | 0.125015 | 0.146889 | 0.563025 | 119 |
| value_composite_raw_industry_neutral_z | 0.0148644 | 0.117406 | 0.126607 | 0.579832 | 119 |
| value_composite_raw_z | 0.011565 | 0.19996 | 0.0578368 | 0.504202 | 119 |
| bp_z | 0.00842358 | 0.210962 | 0.0399293 | 0.529412 | 119 |
| sp_z | 0.00793929 | 0.175326 | 0.0452829 | 0.495798 | 119 |
| value_composite_raw_industry_size_neutral_z | 0.00752134 | 0.101091 | 0.0744019 | 0.579832 | 119 |
| bp_industry_size_neutral_z | 0.00676828 | 0.10428 | 0.0649048 | 0.546218 | 119 |
| sp_industry_neutral_z | 0.00479888 | 0.105213 | 0.0456111 | 0.521008 | 119 |
| value_composite_raw_size_neutral_z | -0.00175697 | 0.178773 | -0.00982795 | 0.478992 | 119 |
| sp_industry_size_neutral_z | -0.00250297 | 0.0882355 | -0.0283669 | 0.495798 | 119 |
| sp_size_neutral_z | -0.00546849 | 0.163877 | -0.0333695 | 0.487395 | 119 |
| bp_size_neutral_z | -0.00818514 | 0.187717 | -0.0436035 | 0.470588 | 119 |

## Grouped Long-Short Summary

| factor_name | mean_long_short_return | std_long_short_return | observations |
| --- | --- | --- | --- |
| cfp_z | 0.00556604 | 0.0350913 | 119 |
| ep_industry_neutral_z | 0.00393684 | 0.0360015 | 119 |
| cfp_industry_neutral_z | 0.00273241 | 0.0266816 | 119 |
| ep_industry_size_neutral_z | 0.00249318 | 0.0386887 | 119 |
| cfp_size_neutral_z | 0.00236331 | 0.0415369 | 119 |
| cfp_industry_size_neutral_z | 0.000857514 | 0.0285386 | 119 |
| bp_industry_neutral_z | 0.000392846 | 0.0382506 | 119 |
| ep_size_neutral_z | 0.000229877 | 0.0533692 | 119 |
| ep_z | 1.00991e-05 | 0.0519814 | 119 |
| value_composite_raw_industry_neutral_z | -0.00216916 | 0.0381211 | 119 |
| sp_z | -0.00426073 | 0.055323 | 119 |
| bp_industry_size_neutral_z | -0.00436093 | 0.0316011 | 119 |
| sp_industry_neutral_z | -0.00461953 | 0.03618 | 119 |
| value_composite_raw_z | -0.00466274 | 0.0605981 | 119 |
| sp_industry_size_neutral_z | -0.00554814 | 0.0325108 | 119 |
| bp_z | -0.00598623 | 0.0612956 | 119 |
| value_composite_raw_industry_size_neutral_z | -0.007155 | 0.0333867 | 119 |
| sp_size_neutral_z | -0.00716149 | 0.0500026 | 119 |
| value_composite_raw_size_neutral_z | -0.00968485 | 0.0533162 | 119 |
| bp_size_neutral_z | -0.0116912 | 0.0542268 | 119 |

## Fama-MacBeth Summary

| term | mean_coefficient | newey_west_se | t_stat | observations |
| --- | --- | --- | --- | --- |
| intercept | 0.0118081 | 0.0052866 | 2.23359 | 119 |
| bp_z | -0.00521603 | 0.0037756 | -1.38151 | 119 |
| ep_z | 0.00105258 | 0.00165815 | 0.634793 | 119 |
| sp_z | 9.95984e-05 | 0.00537379 | 0.0185341 | 119 |
| cfp_z | 0.00200903 | 0.00149892 | 1.34032 | 119 |
| value_composite_raw_z | 0.00220073 | 0.00866254 | 0.254051 | 119 |

## Descriptive Statistics

| factor_name | mean | std | median | p05 | p95 | missing_rate | skew | kurtosis | mean_ticker_autocorr_lag1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bp_z | 0 | 1.00002 | -0.322688 | -0.984604 | 2.09739 | 0.00887365 | 1.69093 | 3.12027 | 0.909702 |
| ep_z | 8.17597e-18 | 1.00002 | -0.086556 | -1.06127 | 1.52572 | 0.0168281 | 0.415615 | 10.2416 | 0.830501 |
| sp_z | 0 | 1.00002 | -0.360573 | -0.664205 | 2.21905 | 0.0811002 | 2.90313 | 9.51334 | 0.751413 |
| cfp_z | 1.63425e-17 | 1.00002 | -0.131429 | -1.00459 | 1.45924 | 0.0162625 | 2.35015 | 14.8724 | 0.803021 |
| value_composite_raw_z | -3.24414e-17 | 1.00002 | -0.330426 | -0.853719 | 2.13833 | 0.00887365 | 2.32801 | 6.42147 | 0.838517 |
| bp_size_neutral_z | 0 | 1.00002 | -0.269269 | -1.12151 | 1.99844 | 0.00887365 | 1.43949 | 2.47976 | 0.89196 |
| bp_industry_neutral_z | -3.24414e-17 | 1.00002 | -0.0292539 | -1.4156 | 1.68234 | 0.00887365 | 0.136622 | 3.14852 | 0.900601 |
| bp_industry_size_neutral_z | 0 | 1.00002 | 0.00470254 | -1.48965 | 1.69362 | 0.00887365 | -0.0495418 | 2.78353 | 0.874917 |
| ep_size_neutral_z | 8.17597e-18 | 1.00002 | -0.0672329 | -1.31854 | 1.5719 | 0.0168281 | 0.231569 | 7.16602 | 0.852937 |
| ep_industry_neutral_z | -1.2264e-17 | 1.00002 | 0.0633136 | -1.31667 | 1.21579 | 0.0168281 | -1.6594 | 11.3893 | 0.784913 |
| ep_industry_size_neutral_z | 2.04399e-18 | 1.00002 | 0.0625013 | -1.3468 | 1.26843 | 0.0168281 | -1.54183 | 9.44251 | 0.789366 |
| sp_size_neutral_z | 0 | 1.00002 | -0.294811 | -0.912407 | 2.19441 | 0.0811002 | 2.39206 | 6.8908 | 0.772246 |
| sp_industry_neutral_z | 8.74783e-18 | 1.00002 | -0.0624293 | -1.32432 | 1.77139 | 0.0811002 | 1.22906 | 6.68289 | 0.749162 |
| sp_industry_size_neutral_z | 0 | 1.00002 | -0.0367737 | -1.32741 | 1.70298 | 0.0811002 | 1.10245 | 5.77674 | 0.755352 |
| cfp_size_neutral_z | 0 | 1.00002 | -0.0955872 | -1.22644 | 1.5641 | 0.0162625 | 1.72029 | 10.4987 | 0.814747 |
| cfp_industry_neutral_z | -2.04282e-18 | 1.00002 | 0.00466048 | -1.43712 | 1.37276 | 0.0162625 | 0.344102 | 9.24511 | 0.788584 |
| cfp_industry_size_neutral_z | -4.08563e-18 | 1.00002 | 0.00579941 | -1.456 | 1.45469 | 0.0162625 | 0.385654 | 7.79908 | 0.778309 |
| value_composite_raw_size_neutral_z | 0 | 1.00002 | -0.28689 | -1.04262 | 2.06931 | 0.00887365 | 1.8286 | 4.19742 | 0.815114 |
| value_composite_raw_industry_neutral_z | 0 | 1.00002 | -0.0357687 | -1.34738 | 1.66274 | 0.00887365 | 0.454188 | 5.15519 | 0.828687 |
| value_composite_raw_industry_size_neutral_z | 1.62207e-17 | 1.00002 | -0.00305001 | -1.42529 | 1.68606 | 0.00887365 | 0.289997 | 3.82477 | 0.809399 |

## Method Notes

- BP, EP, SP, and CFP use `announcement_date` aligned point-in-time financial data.
- Forward returns use next monthly adjusted close from the dynamic HS300 panel.
- Neutralized variants compare size-only, industry-only, and industry plus size residual factors.