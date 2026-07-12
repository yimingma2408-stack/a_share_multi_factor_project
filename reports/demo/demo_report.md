# A-Share Factor Failure Monitoring Demo

## Executive Summary

This resume-oriented demo uses the dynamic HS300 market dataset and five core price/volume factors. It is designed to demonstrate a reproducible factor-monitoring workflow, not to claim a live trading strategy.

- Historical dynamic universe: **627 distinct stocks**.
- Average active universe: approximately **296 stocks per period**.
- Monthly stock selection: top 20% of the valid universe, typically **about 50–60 stocks**.
- Core factors: reversal, three-month momentum, low volatility, low turnover, and liquidity.
- Pipeline runtime using cached data: 2.9 seconds.

## 1. Which factors are stable?

`factor_summary.csv` contains weekly Rank IC, ICIR, long-short return, coverage and the latest lifecycle state. The latest state distribution is `{'Healthy': 0.4448, 'Dormant': 0.3644, 'Watch': 0.1125, 'Decaying': 0.0606, 'Recovering': 0.0178}`. Healthy and Recovering states are treated as monitoring labels, not automatic buy signals.

## 2. Which factors show structural drift?

EOT compares a 156-week base distribution with a 26-week recent distribution using `(RankIC, LSReturn, DownsideReturn)`. The primary smoothed signal uses EWMA half-life 8. High drift is a warning that the factor's joint performance distribution has changed; it is not interpreted as a standalone return forecast.

## 3. Does EOT help identify factor state changes?

The lifecycle labels combine past-only historical ICIR, recent ICIR, quality trend and the expanding historical percentile of smoothed drift. Early periods with insufficient history are Dormant. The state timeline and drift timeline are provided as the main visual evidence.

## 4. Does EOT add allocation value?

The demo compares equal-factor, ICIR-weighted and conservative EOT-penalty weighting in a monthly walk-forward backtest. At 10 bps, the best observed strategy is `equal` with Sharpe `0.444`. The intended conclusion is that EOT has primary monitoring value and only experimental secondary allocation value. Results are historical and not evidence of live tradability.

## Method and safeguards

- Forward returns are computed after factor values and are never inputs to factor construction.
- Monthly signals use the latest weekly signal no later than the rebalance date.
- ST and suspended stocks are filtered; the portfolio takes the top 20% of valid stocks with equal stock weights.
- Costs are tested at 0, 10 and 20 bps one-way.
- Financial, industry and free-float-cap proxy extensions are intentionally excluded from headline backtests and remain experimental future work.

## Limitations and positioning

The dynamic HS300 constituent history, adjusted-price vendor assumptions, simplified execution, approximate costs and lack of revision-aware fundamentals limit inference. This is best presented as an **A-share factor failure-monitoring prototype with EOT**, not as a validated live strategy.
