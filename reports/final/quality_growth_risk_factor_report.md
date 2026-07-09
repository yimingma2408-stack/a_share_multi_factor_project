# Quality, Growth, and Risk Factor Research

- Universe: dynamic HS300 monthly observations with point-in-time fundamentals.
- Fundamental rows: 28286
- Fundamental tickers: 241
- Usable tickers with quality/growth fields: 224
- Research rows after return merge: 28286
- Date range: 2016-01-29 to 2025-12-31

## Factor Definitions

- `size`: log market capitalization.
- `roe`: net profit / book equity.
- `gross_profitability`: gross profit / total assets, where gross profit is revenue minus operating cost.
- `ocf_to_assets`: operating cash flow / total assets.
- `revenue_growth`: year-over-year revenue growth using four-report lag.
- `earnings_growth`: year-over-year net profit growth using four-report lag.
- `rolling_beta`: 252-trading-day rolling beta versus equal-weight dynamic HS300 member return.
- `idiosyncratic_volatility`: annualized volatility of rolling market-model residuals.
- `downside_beta`: 252-trading-day rolling beta estimated only on negative benchmark-return days.

## Rank IC Summary

| factor_name | mean_rank_ic | std_rank_ic | rank_icir | rank_ic_win_rate | observations |
| --- | --- | --- | --- | --- | --- |
| ocf_to_assets_z | 0.0322419 | 0.117304 | 0.274858 | 0.596639 | 119 |
| gross_profitability_z | 0.0314837 | 0.15171 | 0.207526 | 0.563025 | 119 |
| roe_neutral_z | 0.0299282 | 0.105921 | 0.282551 | 0.655462 | 119 |
| roe_z | 0.0293811 | 0.161707 | 0.181693 | 0.563025 | 119 |
| ocf_to_assets_neutral_z | 0.028377 | 0.100295 | 0.282935 | 0.596639 | 119 |
| gross_profitability_neutral_z | 0.0242189 | 0.0967924 | 0.250215 | 0.596639 | 119 |
| earnings_growth_z | 0.0173784 | 0.13092 | 0.132741 | 0.554545 | 110 |
| earnings_growth_neutral_z | 0.0168336 | 0.0958223 | 0.175675 | 0.559633 | 109 |
| revenue_growth_z | 0.011141 | 0.123515 | 0.0901993 | 0.518182 | 110 |
| revenue_growth_neutral_z | 0.00783769 | 0.0904782 | 0.0866252 | 0.486239 | 109 |
| downside_beta_neutral_z | -0.00711841 | 0.116001 | -0.061365 | 0.477876 | 113 |
| size_z | -0.0137362 | 0.162926 | -0.0843095 | 0.445378 | 119 |
| rolling_beta_neutral_z | -0.0162482 | 0.133373 | -0.121825 | 0.433628 | 113 |
| downside_beta_z | -0.0185979 | 0.192345 | -0.0966907 | 0.433628 | 113 |
| idiosyncratic_volatility_neutral_z | -0.0233858 | 0.13655 | -0.171262 | 0.420561 | 107 |
| rolling_beta_z | -0.0253592 | 0.217589 | -0.116546 | 0.460177 | 113 |
| idiosyncratic_volatility_z | -0.0300758 | 0.207606 | -0.14487 | 0.411215 | 107 |

## Grouped Long-Short Summary

| factor_name | mean_long_short_return | std_long_short_return | observations |
| --- | --- | --- | --- |
| ocf_to_assets_z | 0.00806453 | 0.0382655 | 119 |
| gross_profitability_neutral_z | 0.00781077 | 0.0301656 | 119 |
| roe_neutral_z | 0.00754826 | 0.0329136 | 119 |
| idiosyncratic_volatility_z | 0.00748248 | 0.0635439 | 107 |
| ocf_to_assets_neutral_z | 0.0071364 | 0.0315812 | 119 |
| gross_profitability_z | 0.00663913 | 0.0441203 | 119 |
| earnings_growth_neutral_z | 0.00564852 | 0.031009 | 109 |
| revenue_growth_neutral_z | 0.00541712 | 0.0275426 | 109 |
| downside_beta_z | 0.00530906 | 0.0582781 | 113 |
| revenue_growth_z | 0.00493318 | 0.0417285 | 110 |
| rolling_beta_z | 0.0048716 | 0.0621822 | 113 |
| downside_beta_neutral_z | 0.00486178 | 0.0388086 | 113 |
| idiosyncratic_volatility_neutral_z | 0.00428044 | 0.0442522 | 107 |
| earnings_growth_z | 0.00425149 | 0.0424293 | 110 |
| roe_z | 0.00418662 | 0.0490406 | 119 |
| rolling_beta_neutral_z | 0.00374993 | 0.0432857 | 113 |
| size_z | -0.0110365 | 0.049778 | 119 |

## Fama-MacBeth Summary

| term | mean_coefficient | newey_west_se | t_stat | observations |
| --- | --- | --- | --- | --- |
| intercept | 0.0111865 | 0.00573149 | 1.95176 | 107 |
| size_z | -0.00272004 | 0.00157702 | -1.7248 | 107 |
| roe_z | 0.00169469 | 0.0020754 | 0.816563 | 107 |
| gross_profitability_z | 0.00169898 | 0.00294472 | 0.576958 | 107 |
| ocf_to_assets_z | 0.000431031 | 0.00198423 | 0.217228 | 107 |
| revenue_growth_z | 0.00121236 | 0.00114706 | 1.05693 | 107 |
| earnings_growth_z | 0.000500578 | 0.000865803 | 0.578166 | 107 |
| rolling_beta_z | 0.00143658 | 0.00254896 | 0.563596 | 107 |
| idiosyncratic_volatility_z | 0.000957873 | 0.00176656 | 0.542226 | 107 |
| downside_beta_z | 0.00145406 | 0.0024391 | 0.596146 | 107 |

## Descriptive Statistics

| factor_name | mean | std | median | p05 | p95 | missing_rate | skew | kurtosis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| size_z | -5.41746e-17 | 1.00002 | -0.0397731 | -1.60827 | 1.82092 | 0.00887365 | 0.219809 | 0.118151 |
| roe_z | -2.99965e-17 | 1.00002 | -0.125668 | -1.29133 | 1.65619 | 0.0191614 | 0.958708 | 6.32606 |
| gross_profitability_z | -1.70173e-17 | 1.00002 | -0.233322 | -1.13401 | 2.00178 | 0.0811002 | 1.78414 | 5.81189 |
| ocf_to_assets_z | 9.99065e-18 | 1.00002 | -0.0818015 | -1.45774 | 1.71445 | 0.0162625 | 1.10376 | 5.96446 |
| revenue_growth_z | 1.16062e-17 | 1.00002 | -0.228973 | -1.12456 | 1.75066 | 0.172135 | 1.94193 | 7.05366 |
| earnings_growth_z | -3.93533e-18 | 1.00002 | -0.0867226 | -0.867444 | 1.22959 | 0.114332 | 0.964469 | 18.1539 |
| rolling_beta_z | 3.74709e-17 | 1.00002 | 0.00522068 | -1.61138 | 1.6931 | 0.0514035 | 0.0136214 | -0.293365 |
| idiosyncratic_volatility_z | 1.44163e-17 | 1.00002 | -0.0827361 | -1.51774 | 1.79456 | 0.10263 | 0.396936 | 0.0586152 |
| downside_beta_z | 3.00539e-17 | 1.00002 | -0.0136864 | -1.64062 | 1.67742 | 0.0513328 | -4.87906e-05 | -0.0588298 |
| roe_neutral_z | -1.47261e-18 | 1.00002 | -0.0113541 | -1.51487 | 1.60715 | 0.0191614 | 0.323379 | 4.00206 |
| gross_profitability_neutral_z | -2.66536e-18 | 1.00002 | -0.00722837 | -1.4449 | 1.75395 | 0.0811002 | 0.838107 | 4.0165 |
| ocf_to_assets_neutral_z | 1.21292e-18 | 1.00002 | 0.0031374 | -1.58827 | 1.6936 | 0.0162625 | 0.100018 | 2.70099 |
| revenue_growth_neutral_z | 4.77721e-18 | 1.00002 | 0.0101523 | -1.48858 | 1.65146 | 0.178392 | 0.84045 | 4.18249 |
| earnings_growth_neutral_z | 2.67857e-19 | 1.00002 | -0.0234097 | -1.24435 | 1.31183 | 0.120802 | 0.714089 | 10.9905 |
| rolling_beta_neutral_z | -1.33425e-19 | 1.00002 | -0.00143477 | -1.70406 | 1.74889 | 0.0586509 | -0.105344 | 0.745204 |
| idiosyncratic_volatility_neutral_z | -1.40835e-19 | 1.00002 | 0.00108666 | -1.62134 | 1.75219 | 0.108181 | 0.281725 | 0.635852 |
| downside_beta_neutral_z | 1.40086e-18 | 1.00002 | -0.000798718 | -1.72565 | 1.67743 | 0.0585802 | -0.16339 | 0.750915 |

## Method Notes

- Fundamental factors use `announcement_date` aligned point-in-time data.
- Neutralized variants are industry plus size residual factors, except `size` itself.
- Risk factors are computed from daily returns and sampled at monthly rebalance dates.