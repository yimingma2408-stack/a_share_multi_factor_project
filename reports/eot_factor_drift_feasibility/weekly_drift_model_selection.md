# Weekly Drift Model Selection

## Decision

**Primary monitoring signal + conservative secondary allocation penalty.** The allocation result is an experimental extension, not the main claim.

## Selection

- Most statistically smooth signal by low standard deviation and persistence: `ewma_hl12`.
- Selected robust allocation candidate: `ICIR + weekly 4w_mean eta=1.5 clip_0.5`.
- Zero-cost Sharpe 0.487 versus ICIR 0.413; Calmar 0.233 versus 0.173.
- At 20 bps, candidate Sharpe 0.425 versus ICIR 0.351.
- Candidate max drawdown -31.31%; average monthly turnover 45.49%.

Robust selection requires eta <= 1.5 and a penalty floor of at least 0.5. Clipping is useful because it bounds the response to a drift spike. The selected scheme is preferred for its joint Sharpe, Calmar, drawdown, turnover, cost resilience, and non-extreme parameterization, not because it has the single highest raw return.

## Baseline Comparison

| strategy_name                          |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   average_turnover |
|:---------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|
| Equal-factor                           |       0.0170611 |            0.171192 | 0.181322 |      -0.374096 | 0.0456062 |           0.450432 |
| ICIR                                   |       0.0586011 |            0.173519 | 0.412704 |      -0.337782 | 0.173488  |           0.441503 |
| ICIR + monthly EOT drift               |       0.0499465 |            0.164375 | 0.375776 |      -0.291846 | 0.17114   |           0.448908 |
| ICIR + weekly 4w_mean eta=1.5 clip_0.5 |       0.0729019 |            0.17506  | 0.487165 |      -0.313138 | 0.232811  |           0.454863 |
| ICIR + weekly EOT drift, previous      |       0.0688562 |            0.175071 | 0.465458 |      -0.301447 | 0.228419  |           0.4673   |

## Resume Judgment

The project is suitable for a resume as a research prototype. Describe factor failure monitoring as the core contribution and drift-aware weighting as an experimental validation. Do not present the backtest as directly tradable.

Missing requested existing inputs: None.