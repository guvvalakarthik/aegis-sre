# Deep-learning log anomaly protocol

Log messages are normalized before vocabulary construction: secret-like fields, UUIDs, and
numeric identifiers are replaced with stable placeholders. Sequences are bounded, left-truncated,
and padded positions are masked.

LSTM and sequence autoencoder paths use recurrent encoders; the BERT-style path uses a local
Transformer encoder with pinned configuration. No model is downloaded implicitly. All paths
produce masked token-level logits, and anomaly scores are mean negative log likelihood over real
tokens only.

Parser/vocabulary versions, model configuration, dataset/split lineage, seed, and model version
are checkpointed. Novel templates, partial logs, and OOD services require explicit evaluation
reports. This PR provides deterministic contracts without fabricating quality or cost metrics.
