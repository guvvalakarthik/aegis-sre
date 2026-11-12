# Deep-learning telemetry protocol

LSTM, autoencoder, and TCN models share a [batch, time, feature] reconstruction interface.
Training is seeded and deterministic, uses only caller-provided training batches, selects the
checkpoint by validation loss with early stopping, and calibrates anomaly thresholds from
validation reconstruction errors only.

Checkpoints include model configuration, dataset version, split hash, feature schema version,
model version, training history, and state dict. Test data is never used for fitting or threshold
selection. Required evaluation compares T-01/T-02 baselines on frozen data and reports per-
scenario quality, calibration, latency, memory, and training cost.

OOD, rare incidents, and slow degradation are explicit failure modes for the eventual model
card. This PR provides reproducible training/checkpoint contracts without fabricating metrics.
