# Weekly EOT Drift Robustness Report

## 1. Executive Summary

Weekly EOT drift is mainly useful as a **primary monitoring signal with a conservative secondary allocation penalty**. It is not supported as a standalone main allocation signal.

The selected robust candidate is `ICIR + weekly ewma_hl8 eta=1.0 clip_0.5`. It improves zero-cost Sharpe from 0.447 to 0.481 and Calmar from 0.222 to 0.257. At 20 bps its Sharpe is 0.415, compared with 0.382 for ICIR. These are feasibility results, not evidence of tradability.

## 2. Why Weekly Drift Needed Robustness Testing

The previous four-week weekly signal improved return and Sharpe but increased maximum drawdown and turnover. Its weak relationship with subsequent factor returns also raised the risk that direct weighting was reacting to contemporaneous noise. This round therefore tests smoothing, bounded penalties, and transaction costs on a common sample.

The original monthly drift used only six observations in its recent window and was vulnerable to single-month noise. Weekly drift increased the recent window to 26 observations and produced about 4.22 times as many drift observations, making it a more stable monitoring panel. In the previous weekly allocation test, Sharpe and annual return improved relative to ICIR, while drawdown and turnover worsened; that allocation trade-off is the central risk tested here.

## 3. Smoothing Results

| signal_name   |         mean |      std |    median |      min |     max |   autocorrelation_1 |   autocorrelation_3 |   missing_ratio | notes                                                                          |
|:--------------|-------------:|---------:|----------:|---------:|--------:|--------------------:|--------------------:|----------------:|:-------------------------------------------------------------------------------|
| 4w_mean       |  0.0387967   | 1.09788  | -0.137436 | -2.21651 | 4.91842 |            0.797607 |            0.236798 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| 8w_mean       |  0.0168793   | 1.0267   | -0.135093 | -2.11956 | 4.31604 |            0.85397  |            0.266901 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| 12w_mean      |  0.00213966  | 0.957849 | -0.130771 | -2.09342 | 3.78054 |            0.888852 |            0.318994 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| ewma_hl4      |  0.0113737   | 0.907944 | -0.135736 | -1.89586 | 3.62528 |            0.884773 |            0.361183 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| ewma_hl8      | -0.000945118 | 0.73299  | -0.135695 | -1.56945 | 2.85467 |            0.920727 |            0.503856 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| ewma_hl12     | -0.00704134  | 0.618727 | -0.118451 | -1.28998 | 2.29768 |            0.937571 |            0.590284 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |

`ewma_hl12` has the lowest pooled standard deviation with high persistence. The final model selection also considers portfolio behavior, so the smoothest statistical signal is not automatically selected.

## 4. Penalty Clipping Results

The robust candidate uses `clip_0.5` with eta=1.0. Clipping limits factor-weight reactions to isolated drift spikes. Aggressive eta=2.0/no-clipping configurations were excluded from robust selection even when their in-sample metric was attractive.

## 5. Backtest Grid Results

| strategy_name                           |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   average_turnover |
|:----------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|
| Equal-factor                            |       0.0326968 |            0.162915 | 0.276191 |      -0.347212 | 0.0941698 |           0.455352 |
| ICIR                                    |       0.0648558 |            0.173174 | 0.446924 |      -0.291746 | 0.222302  |           0.464685 |
| ICIR + monthly EOT drift                |       0.0673477 |            0.169343 | 0.467091 |      -0.285687 | 0.23574   |           0.452384 |
| ICIR + weekly EOT drift, previous       |       0.0741493 |            0.179606 | 0.485414 |      -0.305604 | 0.242632  |           0.485748 |
| ICIR + weekly ewma_hl8 eta=1.0 clip_0.5 |       0.0719622 |            0.175382 | 0.481334 |      -0.280482 | 0.256566  |           0.479533 |

The selected candidate has annual return 7.20%, volatility 17.54%, max drawdown -28.05%, and average monthly turnover 47.95%. Transaction costs are deducted as simple holdings-change turnover times one-way bps; return-drift-adjusted turnover, impact, and slippage are not modeled.

## 6. Monitoring Diagnostics

High drift does not consistently predict lower future factor long-short returns or Rank IC across factors and horizons. Weekly EOT drift is better interpreted as a contemporaneous factor instability indicator rather than a strong predictor of future factor returns. It is appropriate for dashboard warnings and, at most, a clipped secondary penalty.

## 7. Recommended Project Positioning

**Recommended title: EOT-based Factor Lifecycle Diagnostics with Experimental Drift-aware Weighting.**

This title accurately emphasizes the strongest contribution, factor monitoring, while preserving the allocation experiment without overstating it.

## 8. Limitations

1. Industry and size neutralization are still missing.
2. Transaction costs, slippage, and market impact are not modeled strictly.
3. Strict limit-up/limit-down buy filters are missing.
4. The price-volume factor set has weak standalone alpha.
5. EOT drift still overlaps with mean and covariance shift.
6. High drift has a weak and factor-dependent relationship with future returns.
7. The sample is concentrated in the HS300 and excludes CSI 500 and the full A-share universe.
8. Results must not be described as a directly tradable strategy.

## 9. Next Steps

1. Add industry and market-cap neutralization.
2. Add strict transaction costs and buyability filters.
3. Extend to CSI 500 or the full A-share universe.
4. Add benchmark-relative excess returns.
5. Keep weekly drift as the primary dashboard signal.
6. Use only conservative clipped penalties for dynamic weighting.
7. Test subperiod and style-cycle stability.

## 10. Resume Wording

**English:** Built an A-share multifactor research prototype that models weekly factor-performance distributions and applies entropic optimal transport drift scores for factor failure monitoring; evaluated conservative drift-aware weighting as an experimental extension with smoothing, clipping, and transaction-cost sensitivity, without claiming production tradability.

**中文：**构建 A 股多因子研究原型，基于周度因子表现分布与熵正则最优传输（EOT）漂移分数开展因子失效监控，并将平滑、裁剪后的动态调权作为扩展验证；结果定位为研究可行性分析，不夸大实盘收益。

Missing requested existing inputs: None.