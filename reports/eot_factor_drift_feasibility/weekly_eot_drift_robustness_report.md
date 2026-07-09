# Weekly EOT Drift Robustness Report

## 1. Executive Summary

Weekly EOT drift is mainly useful as a **primary monitoring signal with a conservative secondary allocation penalty**. It is not supported as a standalone main allocation signal.

The selected robust candidate is `ICIR + weekly 4w_mean eta=1.5 clip_0.5`. It improves zero-cost Sharpe from 0.413 to 0.487 and Calmar from 0.173 to 0.233. At 20 bps its Sharpe is 0.425, compared with 0.351 for ICIR. These are feasibility results, not evidence of tradability.

## 2. Why Weekly Drift Needed Robustness Testing

The previous four-week weekly signal improved return and Sharpe but increased maximum drawdown and turnover. Its weak relationship with subsequent factor returns also raised the risk that direct weighting was reacting to contemporaneous noise. This round therefore tests smoothing, bounded penalties, and transaction costs on a common sample.

The original monthly drift used only six observations in its recent window and was vulnerable to single-month noise. Weekly drift increased the recent window to 26 observations and produced about 4.22 times as many drift observations, making it a more stable monitoring panel. In the previous weekly allocation test, Sharpe and annual return improved relative to ICIR, while drawdown and turnover worsened; that allocation trade-off is the central risk tested here.

## 3. Smoothing Results

| signal_name   |      mean |      std |     median |      min |     max |   autocorrelation_1 |   autocorrelation_3 |   missing_ratio | notes                                                                          |
|:--------------|----------:|---------:|-----------:|---------:|--------:|--------------------:|--------------------:|----------------:|:-------------------------------------------------------------------------------|
| 4w_mean       | 0.0845696 | 1.19831  | -0.107914  | -3.53759 | 4.97467 |            0.825158 |            0.335793 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| 8w_mean       | 0.072418  | 1.14507  | -0.121289  | -2.9949  | 4.66018 |            0.876356 |            0.36836  |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| 12w_mean      | 0.06764   | 1.09616  | -0.101033  | -2.76666 | 4.47105 |            0.905017 |            0.415176 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| ewma_hl4      | 0.0729856 | 1.04103  | -0.0830576 | -2.3463  | 4.50713 |            0.905422 |            0.467746 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| ewma_hl8      | 0.0693755 | 0.881845 | -0.0409641 | -1.75324 | 3.86497 |            0.936912 |            0.593624 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |
| ewma_hl12     | 0.0655388 | 0.767554 | -0.0479647 | -1.43142 | 3.43798 |            0.950416 |            0.663589 |        0.373109 | Autocorrelations are averages of factor-level monthly signal autocorrelations. |

`ewma_hl12` has the lowest pooled standard deviation with high persistence. The final model selection also considers portfolio behavior, so the smoothest statistical signal is not automatically selected.

## 4. Penalty Clipping Results

The robust candidate uses `clip_0.5` with eta=1.5. Clipping limits factor-weight reactions to isolated drift spikes. Aggressive eta=2.0/no-clipping configurations were excluded from robust selection even when their in-sample metric was attractive.

## 5. Backtest Grid Results

| strategy_name                          |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   average_turnover |
|:---------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|
| Equal-factor                           |       0.0170611 |            0.171192 | 0.181322 |      -0.374096 | 0.0456062 |           0.450432 |
| ICIR                                   |       0.0586011 |            0.173519 | 0.412704 |      -0.337782 | 0.173488  |           0.441503 |
| ICIR + monthly EOT drift               |       0.0499465 |            0.164375 | 0.375776 |      -0.291846 | 0.17114   |           0.448908 |
| ICIR + weekly 4w_mean eta=1.5 clip_0.5 |       0.0729019 |            0.17506  | 0.487165 |      -0.313138 | 0.232811  |           0.454863 |
| ICIR + weekly EOT drift, previous      |       0.0688562 |            0.175071 | 0.465458 |      -0.301447 | 0.228419  |           0.4673   |

The selected candidate has annual return 7.29%, volatility 17.51%, max drawdown -31.31%, and average monthly turnover 45.49%. Transaction costs are deducted as simple holdings-change turnover times one-way bps; return-drift-adjusted turnover, impact, and slippage are not modeled.

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