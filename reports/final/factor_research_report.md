# Final A-Share Multifactor Research Report

- Selected value factor for final diagnostic portfolio: `ep_industry_size_neutral_z`.
- Benchmark proxy: equal-weight dynamic HS300 member return from the local adjusted-price panel.
- Completion status: complete for data, value factors, neutralization, single-factor tests, multifactor EOT feasibility, and final diagnostics in this report.

## Performance Overview

| series | annual_return | annual_volatility | sharpe | max_drawdown | calmar | win_rate | observations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| portfolio | 0.147413 | 0.200445 | 0.785461 | -0.275152 | 0.535749 | 0.554622 | 119 |
| hs300_equal_weight_proxy | 0.106911 | 0.187213 | 0.633171 | -0.25487 | 0.419472 | 0.613445 | 119 |
| excess | 0.0370561 | 0.0705858 | 0.551164 | -0.227189 | 0.163107 | 0.563025 | 119 |

## Strict Execution

The strict execution stress applies limit-up/limit-down, suspension and ST tradability flags, then estimates spread, slippage, and market impact costs on rebalance trades.

| series | annual_return | annual_volatility | sharpe | max_drawdown | calmar | win_rate | observations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gross | 0.147413 | 0.200445 | 0.785461 | -0.275152 | 0.535749 | 0.554622 | 119 |
| linear_20bps_net | 0.143036 | 0.200425 | 0.766257 | -0.278166 | 0.514211 | 0.554622 | 119 |
| spread_slippage_market_impact_net | 0.142106 | 0.200402 | 0.762222 | -0.279004 | 0.509333 | 0.554622 | 119 |

| date | turnover | strict_execution_cost | blocked_trade_rate |
| --- | --- | --- | --- |
| 2025-02-28 | 0.0408163 | 7.91124e-05 | 0.0107527 |
| 2025-03-31 | 0.142857 | 0.000329665 | 0.00537634 |
| 2025-04-30 | 0.367347 | 0.000829427 | 0.00529101 |
| 2025-05-30 | 0.0408163 | 9.26378e-05 | 0.00529101 |
| 2025-06-30 | 0.0408163 | 9e-05 | 0.00529101 |
| 2025-07-31 | 0.0816327 | 0.000166099 | 0.00529101 |
| 2025-08-29 | 0.367347 | 0.000768154 | 0.00529101 |
| 2025-09-30 | 0.285714 | 0.000578619 | 0.00529101 |
| 2025-10-31 | 0.244898 | 0.000506776 | 0.00529101 |
| 2025-11-28 | 0.0204082 | 3.81782e-05 | 0 |

## Benchmark Attribution

Benchmark-relative results use the local HS300 equal-weight proxy. The market regression below estimates alpha and beta versus that benchmark; industry attribution compares portfolio industry weights with benchmark industry weights; style exposure reports average factor tilts.

### market regression

| alpha | beta | alpha_t_stat | beta_t_stat | r_squared | observations |
| --- | --- | --- | --- | --- | --- |
| 0.00322126 | 1.0021 | 1.68903 | 28.7495 | 0.875998 | 119 |

### industry attribution

| industry | active_weight |
| --- | --- |
| C39计算机、通信和其他电子设备制造业 | -0.0434724 |
| D44电力、热力生产和供应业 | 0.0341062 |
| K70房地产业 | 0.0263748 |
| C26化学原料和化学制品制造业 | 0.0217234 |
| C36汽车制造业 | 0.0146863 |
| I65软件和信息技术服务业 | -0.0138561 |
| C27医药制造业 | -0.0119139 |
| J66货币金融服务 | 0.0107153 |
| C37铁路、船舶、航空航天和其他运输设备制造业 | -0.0105513 |
| C13农副食品加工业 | 0.00900308 |

### style exposure

| style | mean_portfolio_exposure |
| --- | --- |
| bp_z | 0.364328 |
| ep_z | 0.876379 |
| sp_z | 0.352049 |
| cfp_z | 0.282715 |
| value_composite_raw_z | 0.423723 |

## Quality, Growth, And Risk Extensions

The extended factor library adds size, ROE, gross profitability, operating cash-flow quality, revenue growth, earnings growth, rolling beta, idiosyncratic volatility, and downside beta. The table below summarizes their Rank IC diagnostics.

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

## Robustness

The robustness checks include subperiod performance, walk-forward/sample-out Rank IC, stock-pool slices, and cost sensitivity from the weekly EOT drift grid.

### subperiod

| subperiod | portfolio_annual_return | portfolio_sharpe | portfolio_max_drawdown | benchmark_annual_return | excess_mean_monthly | observations |
| --- | --- | --- | --- | --- | --- | --- |
| 2016-2019 | 0.220683 | 1.12539 | -0.275152 | 0.102247 | 0.00882653 | 48 |
| 2020-2022 | 0.0755054 | 0.448127 | -0.250888 | 0.120384 | -0.00307768 | 36 |
| 2023-2025 | 0.126579 | 0.683459 | -0.236648 | 0.0995711 | 0.00208356 | 35 |
| sample_out_2023_2025 | 0.126579 | 0.683459 | -0.236648 | 0.0995711 | 0.00208356 | 35 |

### walk-forward

| factor_name | mean_rank_ic | std_rank_ic | rank_icir | rank_ic_win_rate | observations | window |
| --- | --- | --- | --- | --- | --- | --- |
| ep_industry_size_neutral_z | 0.0298984 | 0.114877 | 0.260264 | 0.547619 | 84 | train_pre_2023 |
| ep_industry_size_neutral_z | 0.0537683 | 0.135174 | 0.39777 | 0.685714 | 35 | sample_out_2023_2025 |

### stock-pool

| factor_name | mean_rank_ic | std_rank_ic | rank_icir | rank_ic_win_rate | observations | stock_pool |
| --- | --- | --- | --- | --- | --- | --- |
| ep_industry_size_neutral_z | 0.0344389 | 0.137676 | 0.250144 | 0.567797 | 118 | full_value_coverage |
| ep_industry_size_neutral_z | 0.0561665 | 0.172289 | 0.326002 | 0.655462 | 119 | high_liquidity_half |

### cost sensitivity

| strategy_name | cost_bps | nav | drawdown |
| --- | --- | --- | --- |
| Equal-factor | 0 | 1.1084 | -0.254232 |
| Equal-factor | 5 | 1.09031 | -0.263883 |
| Equal-factor | 10 | 1.07251 | -0.273412 |
| Equal-factor | 20 | 1.03777 | -0.292108 |
| ICIR | 0 | 1.41402 | -0.0416123 |
| ICIR | 5 | 1.39146 | -0.0422554 |
| ICIR | 10 | 1.36925 | -0.0428982 |
| ICIR | 20 | 1.32589 | -0.0441829 |
| ICIR + monthly EOT drift | 0 | 1.34514 | -0.0366019 |
| ICIR + monthly EOT drift | 5 | 1.32335 | -0.0372049 |
| ICIR + monthly EOT drift | 10 | 1.30191 | -0.0378077 |
| ICIR + monthly EOT drift | 20 | 1.26004 | -0.0390124 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.5 | 0 | 1.34221 | -0.0407785 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.5 | 5 | 1.31994 | -0.0414325 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.5 | 10 | 1.29802 | -0.0518948 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.5 | 20 | 1.25527 | -0.0786613 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.7 | 0 | 1.37983 | -0.0407785 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.7 | 5 | 1.35719 | -0.0414325 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.7 | 10 | 1.33491 | -0.0420862 |
| ICIR + weekly 12w_mean eta=0.5 clip_0.7 | 20 | 1.29144 | -0.0609005 |

_Table truncated._

## Reproducibility

Run the cached-data full workflow with `python scripts/run_full_research_pipeline.py --full` inside the `quant` environment. The current run used locally cached raw AkShare/BaoStock data and generated the final report tables under `reports/final/`.