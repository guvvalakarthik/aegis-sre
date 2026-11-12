# Reproducible evaluation dataset protocol

Frozen datasets are content-addressed by canonical rows, split definition, split membership,
provenance, and pipeline version. Published hashes are immutable in DatasetStore; a changed
dataset produces a new hash.

Split strategies include temporal, deterministic stratified-style hashing, and leave-one-
scenario-out. The split definition and seed are persisted. Dataset cards require intended use,
source and label definitions, known biases, OOD scenarios, and limitations.

Reproduction recomputes the exact hash from raw-to-feature rows and the frozen configuration.
Clean-environment runs must verify the hash before a model can train or evaluate. This PR does
not fabricate a catalog or reproduction result.
