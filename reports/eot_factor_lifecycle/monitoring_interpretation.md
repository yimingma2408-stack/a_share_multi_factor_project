# Monitoring Interpretation

High drift is defined from each factor's expanding, past-only 80th percentile. Across factors, high-drift weeks differ from normal weeks by -0.0051 in average subsequent 12-week Rank IC. This is an association, not a causal or tradable forecast.

EOT is most defensible as a **contemporaneous instability detector**: it summarizes joint changes in Rank IC, long-short return and downside return. Predictive-warning value is evaluated in `monitoring_diagnostics.csv` and varies by factor. Allocation value is tested only through a conservative EWMA-HL8 penalty clipped to [0.5, 1.0]. The report does not claim that EOT alone predicts returns or validates a live strategy.
