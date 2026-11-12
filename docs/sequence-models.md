# TCN/LSTM sequence-model protocol

Issue #21 compares TCN and LSTM/GRU models through one SequenceBatch contract. mask=True means a
real timestep; padded values are excluded from pooling and every sequence must contain at least
one real timestep.

Both models use the same feature order, preprocessing version, train/calibration/test split
hash, search budget, seed, metric definitions, and checkpoint schema. Architecture and
window-length ablations must be recorded separately so test data is never used for selection.

Checkpoints contain model configuration, dataset and preprocessing versions, split hash, seed,
and state dict. load_checkpoint reconstructs the model and validates the schema, enabling
reproducibility from configuration. The optional ml dependency group provides PyTorch.

Held-out learning curves, quality, calibration, latency, memory, and training cost are required
before selecting a champion. This PR intentionally does not invent those measurements.
