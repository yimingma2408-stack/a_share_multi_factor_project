# A-Share Factor Failure Monitoring Demo

## Executive summary

This demo evaluates five price/volume factors in the dynamic HS300 universe and uses an EOT-style distribution-drift signal as a factor-failure monitor. The evidence supports a cautious conclusion: the monitoring layer identifies meaningful deterioration, but the drift-based allocation overlay is not yet a performance improvement.

- **Sample:** 2016-04-29 to 2025-12-31, 117 monthly observations and 526 distinct historical constituents.
- **Portfolio breadth:** 231–264 eligible stocks per rebalance; the top 20% rule selected 46–52 stocks.
- **Current warning:** `turnover_1m`, `volatility_1m` are in `Watch` as of 2025-12-26.
- **Backtest headline:** at 10 bps, `icir` ranked first with 6.8% annualized return, 0.414 Sharpe and -27.3% maximum drawdown.
- **EOT allocation result:** EOT-penalty weighting did not improve on plain ICIR weighting; the Sharpe difference was -0.055 and annual-return difference was -0.9% at 10 bps.
- **Implementation disclosure:** 100% of cached observations use the covariance/mean-shift fallback because POT was unavailable when the drift file was generated; these results should therefore be described as fallback drift diagnostics, not full EOT-map estimates.
- Cached pipeline runtime: 2.2 seconds.

## 1. Factor evidence and current lifecycle state

The full-sample factor statistics and latest monitoring signals are shown below. `Full ICIR` is descriptive over the entire sample; the historical and recent ICIR inputs used for the state label are lagged to avoid look-ahead. `Raw drift` is a distance and is therefore non-negative. `Smoothed drift z-score` standardizes raw drift against the factor's own prior expanding history and then applies an 8-week-half-life EWMA, so it can be negative when current drift is below its historical norm.

| Factor | Coverage | Mean Rank IC | Full ICIR | Latest state | Historical ICIR | Recent ICIR | Raw drift | Smoothed drift z-score | Drift percentile |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| turnover_1m | 99.5% | 0.052 | 0.237 | Watch | 0.142 | -0.134 | 2.249 | 0.484 | 69.5% |
| volatility_1m | 100.0% | 0.040 | 0.183 | Watch | 0.149 | -0.148 | 2.163 | 0.059 | 60.1% |
| reversal_1m | 100.0% | 0.015 | 0.078 | Dormant | -0.033 | -0.011 | 1.220 | -0.398 | 43.1% |
| momentum_3m | 100.0% | -0.011 | -0.051 | Dormant | -0.037 | 0.088 | 0.643 | -0.680 | 12.5% |
| liquidity_1m | 100.0% | -0.015 | -0.089 | Dormant | -0.052 | 0.133 | 3.106 | 1.130 | 91.3% |

The strongest full-sample Rank IC consistency came from `turnover_1m` (ICIR 0.237). The latest snapshot nevertheless shows that `turnover_1m`, `volatility_1m` have moved from positive historical ICIR to negative recent ICIR, which is direct evidence of deterioration rather than merely high EOT distance. `liquidity_1m` has the highest current drift percentile (91.3%); because its state is `Dormant`, drift should be interpreted as distribution change, not automatically as factor decay.

![Smoothed factor drift z-score by factor](figures/factor_drift_timeline.png)

## 2. What the lifecycle chart says

The drift input compares a 156-week base distribution with a 26-week recent distribution of Rank IC, long-short return and downside return. The lifecycle model then combines lagged 104-week historical ICIR, lagged 26-week recent ICIR, their change, and the expanding percentile of EWMA-smoothed drift. Early observations without enough history are `Dormant`, so the heatmap should be read from left to right rather than by comparing raw counts of states.

![Factor lifecycle states](figures/lifecycle_state_heatmap.png)

The chart's practical use is monitoring: it separates persistent healthy periods from episodes that deserve review. It does not turn a `Healthy` label into a buy signal or a `Watch` label into an automatic exclusion.

## 3. Walk-forward backtest

The table reports the three allocation rules after a 10 bps one-way turnover charge.

| Strategy | Annual return | Annual volatility | Sharpe* | Max drawdown | Monthly win rate | Average turnover |
| --- | --- | --- | --- | --- | --- | --- |
| icir | 6.8% | 16.4% | 0.414 | -27.3% | 53.4% | 48.7% |
| equal | 6.4% | 16.2% | 0.391 | -37.8% | 56.0% | 45.1% |
| eot_penalty | 5.9% | 16.3% | 0.358 | -27.3% | 50.9% | 48.8% |

![Strategy NAV after 10 bps cost](figures/strategy_nav.png)

At this cost assumption, `icir` delivered the highest risk-adjusted result. EOT-penalty weighting produced 5.9% annualized return and 0.358 Sharpe versus 6.8% and 0.414 for ICIR weighting. Therefore, this run supports distribution drift as a diagnostic overlay, but not the claim that the current penalty function adds allocation value.

The latest weights also illustrate the mechanism: the drift penalty only scales non-negative ICIR signals, with a penalty floor of 0.5.

| Factor | EOT-penalty weight | ICIR weight |
| --- | --- | --- |
| reversal_1m | 20.5% | 12.3% |
| momentum_3m | 12.5% | 7.5% |
| volatility_1m | 0.0% | 0.0% |
| turnover_1m | 0.0% | 0.0% |
| liquidity_1m | 67.0% | 80.2% |

## 4. Transaction-cost sensitivity

Annualized return declines monotonically as the assumed one-way cost rises from 0 to 20 bps:

| Strategy | 0 bps | 10 bps | 20 bps |
| --- | --- | --- | --- |
| eot_penalty | 6.5% | 5.9% | 5.2% |
| equal | 6.9% | 6.4% | 5.8% |
| icir | 7.4% | 6.8% | 6.2% |

![Transaction-cost sensitivity](figures/transaction_cost_sensitivity.png)

The strategies retain positive historical annualized returns at 20 bps, but the gap between gross and net results is material because average monthly turnover is roughly 45%–49%. This is a sensitivity check, not a complete execution model.

## Method and safeguards

- Factor values are constructed before one-month forward returns and never use those forward returns as inputs.
- Monthly rebalances use the latest weekly monitoring signal no later than the rebalance date.
- The active universe requires current HS300 membership, normal trading status and non-ST status.
- Five cross-sectional factor z-scores are combined, and the top 20% of valid stocks are equally weighted.
- `equal` uses equal factor weights; `icir` normalizes positive rolling ICIR; `eot_penalty` additionally scales positive ICIR by smoothed drift.
- The cached drift input uses 156 base weeks and 26 recent weeks; 100% of cached observations use the covariance/mean-shift fallback because POT was unavailable when the drift file was generated.
- Costs are modeled as turnover multiplied by 0, 10 or 20 bps one-way.
- *Sharpe is implemented here as annualized compound return divided by annualized monthly volatility, with no risk-free-rate adjustment.*

## Limitations

The results depend on the reconstructed dynamic HS300 history, adjusted-price vendor conventions and a simplified monthly execution model. The backtest does not model limit-up/limit-down execution, market impact, liquidity capacity or point-in-time fundamental revisions. Industry, fundamentals and free-float-cap neutralization are not included. Most importantly, the current cached drift data use the fallback implementation noted above; full EOT barycentric-map results require regenerating that input with POT available. Thresholds and penalty strength are research choices and have not been validated out of sample.

Accordingly, this project is best presented as an **A-share factor failure-monitoring prototype with an experimental allocation overlay**, not as a validated live strategy.

## Reproducibility and artifacts

- Run: `python scripts/workflows/run_demo.py`
- Factor statistics: [`factor_summary.csv`](factor_summary.csv)
- Backtest statistics: [`backtest_summary.csv`](backtest_summary.csv)
- Cost sensitivity: [`transaction_cost_sensitivity.csv`](transaction_cost_sensitivity.csv)
- Machine-readable lifecycle, weights and NAV files: `../../data/processed/demo/`
