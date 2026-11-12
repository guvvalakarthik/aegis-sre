# Transformer log anomaly protocol

The LogBERT-style model learns masked-token reconstruction over normalized log templates. Masking
is deterministic for a pinned seed and never selects padding. Tokenizer version, model configuration,
dataset/split lineage, and model version are checkpoint metadata.

The model exposes per-token negative log-likelihood anomaly scores and layer/head-aggregated
attention maps. Attention is interpretability evidence, not causal proof. Training batches and
validation batches are frozen inputs; early stopping uses validation loss only.

Novel templates, partial logs, OOD services, latency, memory, training cost, and comparisons with
T-05 and statistical/ML baselines require frozen-dataset execution. This PR does not fabricate
quality or operational metrics.
