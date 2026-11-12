# Log transformer protocol

Issue #23 uses a redaction-first pipeline. Secret-like key/value fields, UUIDs, IP addresses,
long hexadecimal identifiers, and numeric values are removed or normalized before template IDs
or token IDs are generated. Raw messages must not be persisted in model artifacts or logs.

Parser and vocabulary versions are part of every event and sequence. Unknown templates map to
UNK, sequences are truncated from the oldest side to a bounded length, and padding is masked
out of attention and pooling. Service identifiers are bounded and validated.

The transformer checkpoint must include parser version, vocabulary version, dataset version, split
hash, model configuration, and seed. Embeddings and logits are reproducible for a fixed artifact
and evaluation mode.

Required reports include macro F1, rare-class recall, unseen-template robustness, calibration,
latency, memory, and failure cases, compared with TF-IDF/XGBoost and frequency baselines. This
PR provides the secure contracts and model interface but does not fabricate those metrics.
