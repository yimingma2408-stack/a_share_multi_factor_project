# Weekly Drift Model Selection

## Decision

**Primary monitoring signal + conservative secondary allocation penalty.** The allocation result is an experimental extension, not the main claim.

## Selection

- Most statistically smooth signal by low standard deviation and persistence: `ewma_hl12`.
- Selected robust allocation candidate: `ICIR + weekly ewma_hl8 eta=1.0 clip_0.5`.
- Zero-cost Sharpe 0.481 versus ICIR 0.447; Calmar 0.257 versus 0.222.
- At 20 bps, candidate Sharpe 0.415 versus ICIR 0.382.
- Candidate max drawdown -28.05%; average monthly turnover 47.95%.

Robust selection requires eta <= 1.5 and a penalty floor of at least 0.5. Clipping is useful because it bounds the response to a drift spike. The selected scheme is preferred for its joint Sharpe, Calmar, drawdown, turnover, cost resilience, and non-extreme parameterization, not because it has the single highest raw return.

## Baseline Comparison

| strategy_name                           |   annual_return |   annual_volatility |   sharpe |   max_drawdown |    calmar |   average_turnover |
|:----------------------------------------|----------------:|--------------------:|---------:|---------------:|----------:|-------------------:|
| Equal-factor                            |       0.0326968 |            0.162915 | 0.276191 |      -0.347212 | 0.0941698 |           0.455352 |
| ICIR                                    |       0.0648558 |            0.173174 | 0.446924 |      -0.291746 | 0.222302  |           0.464685 |
| ICIR + monthly EOT drift                |       0.0673477 |            0.169343 | 0.467091 |      -0.285687 | 0.23574   |           0.452384 |
| ICIR + weekly EOT drift, previous       |       0.0741493 |            0.179606 | 0.485414 |      -0.305604 | 0.242632  |           0.485748 |
| ICIR + weekly ewma_hl8 eta=1.0 clip_0.5 |       0.0719622 |            0.175382 | 0.481334 |      -0.280482 | 0.256566  |           0.479533 |

## Resume Judgment

The project is suitable for a resume as a research prototype. Describe factor failure monitoring as the core contribution and drift-aware weighting as an experimental validation. Do not present the backtest as directly tradable.

Missing requested existing inputs: None.