# Temporal splits and feature-quality reporting

Issue #16 defines time-aware dataset splits for train, validation, calibration, test, and
unseen-variant OOD evaluation.

## Split rules

Examples are sorted by event time and stable example ID. The split plan records dataset
version, seed, assignments, and a SHA-256 split hash. Recreating the same input with the same
seed produces the same hash.

Scenario variants listed in held_out_variants are never assigned to train, validation,
calibration, or test; they receive the OOD split.

## Point-in-time correctness

Every feature declares when it is available: event time, ingestion time, or offline only.
Offline-only features cannot be consumed by a prediction window. Label time cannot precede
event time. A feature audit must compare the declared availability with the online feature
pipeline.

## Dataset card

Each dataset release must publish:

- collection process and approved sources
- dataset and split versions/hashes
- feature availability and missingness
- class distribution and label latency
- drift baseline and monitoring window
- intended use, out-of-scope use, known bias, and limitations
- privacy, retention, and access controls

The implementation does not fabricate these statistics. They are generated from each real
dataset release and attached to the evaluation evidence.
