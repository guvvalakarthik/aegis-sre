# Feature engineering and dataset protocol

Feature extraction uses a closed-open point-in-time window and ignores records outside it,
including future records. Metrics produce means and p95 values; logs produce counts/error rates;
traces produce latency percentiles and error rates. Missing features are explicit and represented
with finite defaults plus a missing-feature set.

Feature rows include schema version, code/data lineage hash, scenario, service, run, and window
identity. Normalization is fitted only on training rows and rejects schema mismatches. Splits are
deterministic and group by scenario/service/run so windows from one run cannot cross partitions.

Recompute-vs-stored matrix comparison, full feature distributions/correlations/missingness, and
real raw-telemetry validation require the K-09 labels and telemetry pipeline. This PR does not
fabricate catalog statistics.
