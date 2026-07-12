# Leakage Audit

All formal lifecycle features are computed on date *t* using observations dated no later than *t*. Weekly outcomes use the next observed weekly close. Eligibility, ICIR, drift percentiles, clusters, representatives, health scores and weights use shifted rolling/expanding history. Weekly signals are mapped backward to monthly rebalances. Tests assert these boundaries.

Financial factors are not admitted to the formal backtest: announcement dates exist and are as-of aligned, but only five tickers are populated and restatement histories are unavailable. The dynamic universe is date-varying, but fidelity to the vendor's historical constituent publication timestamps cannot be proved from local files. Adjusted-price corporate-action timing is also a vendor assumption. These are documented limitations rather than treated as solved.
