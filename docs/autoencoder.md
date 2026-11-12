# Multivariate autoencoder protocol

Issue #20 uses fixed-length windows with explicit missingness handling. Window length,
feature order, dataset version, split hash, seed, optimizer settings, and checkpoint metadata
must be recorded with every artifact.

The scaler is fitted on approved training windows only. Calibration errors select the anomaly
threshold; the held-out test split is reserved for final evaluation. Reconstruction error is
reported per window, while per-feature mean squared reconstruction contributions provide
attribution.

Training-time requirements include deterministic seeds, early stopping, checkpoint reload,
and runtime metadata (Python, torch, device, batch size, and duration). The required report
must compare against Issues #18 and #19 on identical windows and splits, including detection
quality, calibration, latency, memory, and failure cases.

The module does not fabricate metrics and intentionally keeps the actual torch training loop
behind the research-time dependency boundary until the approved dataset v1 artifact is wired.
