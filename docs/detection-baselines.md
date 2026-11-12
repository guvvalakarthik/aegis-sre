# Statistical detection baselines

Issue #18 provides an interpretable performance floor using the same evaluation windows and
labels as later ML and deep-learning models.

## Detectors

- static threshold
- rolling z-score
- EWMA residual
- seasonal lag baseline
- rolling change-point score

Each detector emits an index, anomaly score, and plain-language explanation. Parameters must
be fitted only on training/calibration data and recorded with the dataset and benchmark
version.

## Metrics

The shared evaluator reports precision, recall, F1, false alarms per hour, and mean detection
delay. Results must also record preprocessing, threshold parameters, sample interval, and
the affected signal.

Compare every detector with two controls:

- always normal
- always anomalous

The implementation does not fabricate benchmark results. Run it against the approved dataset
v1 windows and publish failure cases and computational cost before claiming a baseline winner.
