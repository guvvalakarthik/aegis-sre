# Classical ML training protocol

Issue #19 defines a reproducible training boundary for Isolation Forest and XGBoost.

## Data boundary

Training consumes only the approved train split. Hyperparameters and preprocessing are tuned
on train/calibration data. The held-out test split is read only by the final evaluation command.

Every serialized artifact records model version, dataset version, split hash, feature names, and
calibration version. Deterministic seeds and single-threaded training are the default.

## Models

- Isolation Forest provides an unsupervised anomaly score.
- XGBoost provides supervised incident classification.
- Calibrated probabilities are fitted on the calibration split only.
- Feature importance is reported from the fitted model.
- SHAP values are computed only for prediction-time features that pass the point-in-time
  feature contract.

## Required reports

Publish calibration quality, confidence thresholds, precision/recall/F1/PR-AUC, latency,
memory, training cost, and failure cases. Compare with Issue #18 using identical windows,
labels, dataset version, and split hash.

The module intentionally does not fabricate model results; training and serialization must run
against the approved dataset v1 artifact before the issue is marked complete.
