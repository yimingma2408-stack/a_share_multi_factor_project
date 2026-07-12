# EOT-Map Tests for A-Share Factor Lifecycle Diagnostics

## 1. Executive Summary

The project has been upgraded from an unscaled, distance-based EOT drift diagnostic to a formal common-reference EOT-map statistic with centered IID and block multiplier calibration, coordinate contributions, signed deterioration and test-based lifecycle states. The delivered panel contains 3,165 weekly factor-date tests and 9,495 coordinate rows, each endpoint calibrated with 300 IID and 300 block draws. Turnover and volatility factors reject homogeneity most frequently. Downside return is both the most common largest-change coordinate (2,181/3,165) and the most common dominant-deterioration coordinate (1,564/3,165).

The clearest value is **monitoring**, not allocation. At 10 bps, equal eligible factors have the best observed Sharpe (0.022); all formal test-weighting variants are lower. The block extension improves the dependent-null synthetic rejection rate from 60% to 40%, but remains far above nominal size. The project is suitable as a transparent research/engineering portfolio piece if these caveats remain prominent; no allocation-alpha or live-trading claim is warranted.

## 2. Difference from the Previous Version

The old output was the average squared distance between base and recent barycentric maps. It was neither Sinkhorn transport cost nor a calibrated test. The new implementation retains that unscaled distance, adds `nm/(n+m)` scaling, and compares the scaled statistic with a centered bootstrap null. Raw and FDR-adjusted p-values replace interpretations based only on `eot_drift_zscore`; the old drift panels remain untouched as baselines.

## 3. Method

For factor `j` and date `t`, `Z=(RankIC, LSReturn, DownsideReturn)`. The base sample contains weeks `t-182` through `t-27`; recent contains `t-26` through `t-1`. Median/MAD statistics come only from base and transform both samples. Independent unit-ball references are fixed within a test. Both empirical distributions map from those references with a shared epsilon equal to 0.2 times the pooled standardized median non-zero squared distance.

The sign convention is `D = T_recent - T_base`. The formal statistic is

\[
\mathcal T_{n,m}=\frac{nm}{n+m}\frac1N\sum_l\|D(U_l)\|^2.
\]

## 4. Bootstrap Calibration

IID exponential weights reproduce weighted empirical maps. Null draws use centered increments, not the direct distance between bootstrap maps. The block extension shares a multiplier within consecutive eight-week blocks. IID is the paper-faithful benchmark; block is only a dependence-robust exploratory calibration. The 20-replication synthetic results reveal material dependent-null oversizing and do not establish general size control. See `bootstrap_calibration_report.md`.

The final rolling panel uses 300 draws per IID and block calibration, with zero recorded bootstrap or Sinkhorn failures. A separate 90-row latest-window robustness exercise covers reference sizes 50/100/200, epsilon scales 0.1/0.2/0.5 and block lengths 4/8/13. Rejection rates vary across these finite settings, so the main parameters remain pre-specified rather than selected from backtest performance.

## 5. Global Test Results

Block raw rejection rates are highest for `turnover_1m` (33.2%), `volatility_3m` (33.2%), `volatility_1m` (31.7%), `turnover_3m` (31.6%) and `momentum_3m` (29.4%). Cross-factor FDR rejects 23.4% of all panel rows; 23.4% satisfy the rolling two-of-three persistence rule. IID raw rejection is 19.1%, compared with block raw rejection of 27.1%. These are calibrated sample diagnostics, not definitive population statements.

## 6. Coordinate Diagnostics

Downside return supplies the largest squared-change contribution in 2,181 rows, long-short return in 787 and Rank IC in 197. Dominant deterioration is downside return in 1,564 rows, long-short return in 876 and Rank IC in 725. “Largest change contribution” is deliberately separated from “largest deterioration contribution”; neither is causal attribution.

## 7. Lifecycle States

The panel classifies 1,126 Healthy, 950 Watch, 220 Decaying, 364 Recovering and 505 Dormant observations. Rules combine past-only historical/recent ICIR, quality trend, FDR rejection, persistent warning and signed core-coordinate deterioration. Reasons are stored per row, making states more interpretable than the legacy smoothed-distance threshold.

## 8. Monitoring Value

The test detects joint changes in predictive rank association, long-short payoff and downside behavior and identifies which coordinate dominates. Persistence and FDR reduce reliance on isolated raw p-values. Its strongest defensible role is contemporaneous factor-health monitoring.

## 9. Allocation Value

Seven walk-forward variants compare equal factors, ICIR, old distance penalty, formal significance penalty, signed penalty and two lifecycle filters at 0/5/10/20 bps. At 10 bps, equal weighting leads with Sharpe 0.022; old distance penalty is -0.157, formal significance penalty -0.170 and formal signed penalty -0.173. Thus formal calibration improves interpretability but does **not** add demonstrated allocation value or cost-robust alpha in this sample.

## 10. Limitations

1. Weekly factor performance is serially dependent.
2. IID bootstrap theory does not automatically cover this time series.
3. Block multipliers are an applied extension without matching proof.
4. Rolling windows overlap heavily.
5. Multiple factors/dates create multiplicity beyond cross-sectional BH.
6. Coordinate contribution is not causal attribution.
7. Performance metrics contain estimation noise.
8. Historical results do not guarantee a live strategy.
9. Epsilon/reference-size robustness remains finite and incomplete.
10. Financial factors still require point-in-time-safe, broad coverage.
11. The synthetic study uses 20 replications per scenario and remains too small for precise tail-size inference.
12. Dependence-robust block calibration remains materially oversized under the AR(1) synthetic null.

## 11. Final Project Positioning

Recommended title: **EOT-Map Tests for A-Share Factor Lifecycle Diagnostics** / **基于 EOT-map 两样本检验的 A 股因子生命周期诊断**. Use **Experimental Drift-Aware Multifactor Weighting** only as a secondary extension.

## 12. Resume Wording

中文：

- 构建共同参考分布上的正式 EOT-map 两样本检验，以 centered multiplier bootstrap 校准 A 股因子生命周期变化。
- 将联合统计量分解为 Rank IC、多空收益与下行收益坐标贡献，并用有符号诊断区分改善和恶化。
- 实现 FDR、持续告警、生命周期监控及实验性保守调权，明确区分监控价值与不可验证的实盘收益主张。

English:

- Built a formal common-reference EOT-map two-sample test with centered multiplier-bootstrap calibration for A-share factor lifecycle monitoring.
- Decomposed joint distribution changes into Rank IC, long-short return and downside coordinates with signed deterioration diagnostics.
- Added FDR, persistent warnings, interpretable lifecycle states and conservative experimental weighting while separating monitoring evidence from live-alpha claims.

**30 seconds:** I upgraded a factor-drift prototype into a calibrated EOT-map testing system. It compares three years of weekly factor behavior with the latest six months using common reference maps, centered bootstrap p-values and coordinate-level direction diagnostics. The main result is a more interpretable monitoring framework; weighting is explicitly experimental and did not outperform the equal baseline.

**2 minutes:** The project starts from weekly Rank IC, long-short and downside observations for ten A-share factors. I standardize only with the historical window, map base and recent samples from the same independent unit-ball references, apply the paper's effective-sample-size scaling and calibrate with centered IID exponential multipliers. Because weekly observations are dependent, I also built an eight-week block-multiplier extension and label it exploratory. Global p-values receive cross-factor BH correction and a two-of-three persistence rule; map differences are decomposed by coordinate and signed so lifecycle states can explain whether a change is improvement or deterioration. Finally, I compare seven past-only monthly allocation variants with transaction costs. The tests improved monitoring interpretability, but did not establish cost-robust allocation alpha or a live strategy.
