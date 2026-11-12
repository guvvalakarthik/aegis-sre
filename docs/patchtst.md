# PatchTST forecasting protocol

Issue #22 uses channel-independent temporal patches. Inference accepts only the historical
context tensor with shape [batch, channels, context_length]; future observations and unknown
future covariates are not accepted by the model API. This prevents accidental future leakage.

Patch length, stride, context, horizon, channel order, scaling, model version, seed, and split
hash are configuration inputs and must be persisted with the checkpoint. Calibration thresholds
are computed from validation residuals only. The held-out horizon is used once for final
forecast and anomaly metrics.

Reports must include forecast MAE/RMSE/interval coverage, anomaly precision/recall/PR-AUC,
threshold calibration, streaming latency, memory, and representative failure cases. Ablations
must isolate patch length, context length, horizon, and channel independence. Comparisons use
the same splits and preprocessing as the seasonal, LSTM/TCN, and autoencoder baselines.

This PR provides the leakage-safe model and scoring contracts; it does not invent benchmark
results or claim a champion before the approved dataset and runtime validation are available.
