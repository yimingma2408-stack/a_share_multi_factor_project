# Legacy EOT-Based Factor Lifecycle Diagnostics with Experimental Drift-Aware Weighting

> **Supersession note:** This is the retained distance-based baseline. It does not provide the formal common-reference EOT-map statistic, centered multiplier p-values, FDR or signed coordinate diagnostics. The authoritative current study is `../eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md`.

## 1. Executive Summary

The project was upgraded successfully into a reproducible lifecycle-diagnostics research pipeline. Code contains 31 registered factor definitions; 10 are eligible, 11 watch-only, and 10 rejected in the latest/static eligibility summary. The formal ten-factor market library forms 3 descriptive clusters. Weekly EOT, smoothed drift, lifecycle states, health scores, walk-forward selection, weights and monthly backtests were generated.

At 10 bps, the highest observed Sharpe is `cluster_representative_equal` (0.436 if available). The lifecycle-filtered drift method changes Sharpe versus equal eligible factors by -0.115. This is a historical research comparison, not a live strategy claim.

## 2. Data and Factor Library

The formal sample is the dated dynamic HS300 panel from 2016-01-04 to 2025-12-31. Signals use adjusted prices, returns, turnover and amount; total market cap is merged for cross-sectional neutralization. Industry is unavailable. Fundamental code and announcement-date fields exist, but the current panel contains only five tickers and is excluded from formal allocation tests.

## 3. Eligibility and Data Quality

Eligibility is recomputed from past history. Minimum formal requirements are 52 prior weekly observations, 70% recent coverage and non-degenerate dispersion. Early weeks remain watch-only. Latest/static counts are shown above; rejected factors are fundamentals with inadequate cross-sectional coverage.

## 4. Redundancy and Clustering

Clustering uses 50% average cross-sectional absolute Spearman correlation and 50% factor long-short-return absolute correlation, distance `1-|corr|`, average linkage and a pre-set 0.40 cut. Descriptive highly redundant pairs (combined score >=0.85): reversal_1m/momentum_1m (1.000), turnover_1m/turnover_3m (0.956), volatility_1m/volatility_3m (0.889), turnover_1m/liquidity_1m (0.878). Full-sample clusters are reporting diagnostics only; backtest clusters, redundancy scores and representative selection use information available at each decision date.

## 5. Weekly Factor Performance

See `weekly_factor_performance_summary.csv` for Rank IC, ICIR, long-short return, positive-week ratio, coverage and turnover. Next-week returns are computed after signal construction.

## 6. EOT Lifecycle Diagnostics

EOT uses the three-dimensional vector `(RankIC, LSReturn, DownsideReturn)`, a 156-week base window, 26-week recent window, 100 shared references, epsilon scale 0.1 and seed 42. Energy distance, MMD, mean shift, covariance shift and convergence status are retained. The primary signal is EWMA half-life 8; five alternative smoothers are stored for robustness.

## 7. Lifecycle States

Past-only rolling ICIR, recent ICIR, their trend and expanding drift percentile create Healthy, Watch, Decaying, Dormant and Recovering states. Overall proportions: {"Dormant": 0.4291, "Healthy": 0.4104, "Watch": 0.1079, "Decaying": 0.0367, "Recovering": 0.0158}. Rules are explicit in the pipeline; early insufficient-history observations are Dormant.

## 8. Factor Selection and Weighting

The study compares all eligible, cluster representatives, lifecycle-filtered, Top-K 5/8/10 and family-balanced selections. Weighting compares equal, representative equal, ICIR, ICIR+EOT, redundancy, cost and lifecycle-filtered models. Drift uses `clip(1/(1+max(D,0)),0.5,1)`. Family totals are capped at 65% because only price-volume and risk families are formally represented.

## 9. Backtest Results

Monthly portfolios use the latest weekly signal no later than rebalance, top 20% stock selection and equal stock weights. ST, suspension, approximate limit-up and 120-day observed-history filters apply. See `backtest_summary.csv`. Emphasis belongs on Sharpe, drawdown, Calmar and turnover rather than annual return alone.

## 10. Monitoring Value vs Allocation Value

EOT drift is primarily useful as a **monitoring signal**, with a conservative secondary allocation penalty. It detects contemporaneous joint distribution instability; predictive warning varies by factor. The 10-bps allocation increment versus equal eligible factors is -0.115 Sharpe and must be interpreted alongside turnover, drawdown, regimes and costs.

## 11. Robustness

Results include 0/5/10/20 bps cost sensitivity and pre-set early/late, bull/bear and high/low-volatility regimes. No parameter grid was optimized on the full sample.

## 12. Limitations

The financial panel covers five tickers; announcement revision histories and industry data are absent. Float cap is incomplete, so total cap is used. Historical constituent-publication timing and adjusted-price vendor mechanics cannot be independently verified. The HS300 focus, simplified equal-weight execution, limit-up proxy, linear costs, absent impact model, factor correlation, uneven family counts and EOT overlap with mean shift limit generalization. Historical results do not establish live tradability.

## 13. Final Project Positioning

Recommended title: **A-Share Factor Failure Monitoring with Entropic Optimal Transport**.

## 14. Resume Wording

**中文简历：** 基于动态沪深300样本构建10因子周度生命周期监控框架，使用熵正则最优传输识别因子分布漂移，并以无未来信息的滚动资格筛选、聚类去冗余和保守漂移惩罚完成月度 walk-forward 对照回测；系统评估交易成本、换手、回撤与市场状态稳健性，明确区分监控价值与配置价值。

**English resume:** Built a weekly lifecycle-monitoring framework for 10 A-share factors in a dynamic CSI 300 universe, using entropic optimal transport to diagnose distribution drift and past-only eligibility, redundancy clustering, and conservative drift penalties in monthly walk-forward experiments; evaluated costs, turnover, drawdowns, and regime robustness while separating monitoring value from allocation value.

**30-second interview introduction:** I built an A-share factor failure-monitoring project. Rather than treating EOT drift as a return forecast, I measure joint changes in weekly IC, long-short return and downside behavior, classify factor lifecycle states, and test a clipped secondary weighting penalty with walk-forward controls. The main contribution is a reproducible monitoring system with honest PIT and data-coverage limits.

**2-minute interview introduction:** The project starts from a dynamic CSI 300 daily panel and a registered factor library. I audit point-in-time safety and reject the current fundamental factors from formal tests because only five stocks are populated. For ten research-ready market factors, I apply cross-sectional MAD winsorization, market-cap neutralization and direction standardization, then build next-week Rank IC and long-short distributions. EOT compares a three-year base distribution with the latest six months, while mean shift, covariance shift, energy distance and MMD provide interpretable controls. Past-only ICIR and drift percentiles create Healthy, Watch, Decaying, Dormant and Recovering states. I then compare equal, cluster-aware, ICIR and conservatively clipped drift-aware weights in a monthly walk-forward portfolio with transaction costs and regime tests. The defensible conclusion is monitoring first, allocation second; the exercise is a research prototype, not evidence of live alpha.

## 15. Next Steps

1. Expand PIT financial statements and revision histories to the full dynamic universe.
2. Add dated industry classifications and free-float capitalization.
3. Validate constituent publication timestamps and corporate-action adjustment timing.
4. Add benchmark-relative risk, impact-aware execution and another universe.
5. Run genuinely out-of-sample paper monitoring before considering allocation use.
