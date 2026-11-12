# Transformer telemetry protocol

The model uses fixed temporal patches and multi-head attention over patch tokens. It reconstructs
the original context and returns per-window reconstruction errors. Attention attribution returns
layer/head-aggregated patch-to-patch weights for inspection.

Configuration, dataset version, split hash, feature schema, seed, patch geometry, and model version
are persisted in checkpoints. Training and threshold calibration must use train/validation data
only; held-out data is reserved for final comparison with T-01 through T-03.

Latency, memory, training time, calibration, and per-scenario quality are required operational
measurements. Attention maps are interpretability evidence, not causal proof. This PR does not
fabricate model metrics or claim superiority over the DL baselines.
