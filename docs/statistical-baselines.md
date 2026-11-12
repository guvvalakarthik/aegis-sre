# Statistical baseline protocol

Baselines are deterministic for pinned parameters and data and use prefix-only observations. The
detectors include thresholds, SLO violations, rules, z-score, EWMA, Holt, and seasonal comparison.
Every detection returns a confidence-like score and the exact window used.

Calibration thresholds must use non-incident baseline data only. Evaluation reports precision,
recall, false-alarm rate, and detection latency per scenario and aggregate, generated from frozen
datasets. This PR provides detector and metric contracts without fabricating scenario results.
