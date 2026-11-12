# Data quality and feature quality protocol

Quality validation is a training gate. It reports completeness, schema, freshness, temporal,
target/group leakage, and per-feature variance, label correlation, mutual information, stability
delta, and missing rate. Error-level findings make the report non-trainable and produce actionable
diagnostics.

Temporal leakage rejects feature timestamps after label timestamps. Target-name leakage rejects
features named label/target/outcome/future/recovery, and group leakage rejects a run/group present
in more than one split. Future-dated rows and missing required values are reported.

Run this report automatically before model training. Real incident datasets must publish the full
feature catalog, distributions, correlations, missingness, and injected-leakage validation; this
PR does not fabricate those statistics.
