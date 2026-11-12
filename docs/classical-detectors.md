# Classical anomaly detector protocol

Isolation Forest, One-Class SVM, PCA reconstruction, and ARIMA residual adapters fit only on
caller-provided training data. Dataset version, split hash, feature order, model version, and
seed are stored in metadata. Validation scores calibrate thresholds; test data is not used for
fitting, tuning, or threshold selection.

Detector scores are converted to anomaly flags only after validation calibration. Candidate
selection uses validation scores and stable tie-breaking. Inference measurement records latency;
the deployment layer must add memory and cost measurements.

Isolation Forest is robust for broad outliers, One-Class SVM is sensitive to scaling, PCA is
interpretable but linear, and ARIMA is univariate/temporal. Real frozen-dataset quality,
calibration, per-scenario results, and operational reports remain required validation.
