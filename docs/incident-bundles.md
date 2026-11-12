# Incident bundles and replay

Issue #14 defines incident-bundle.v1 as the boundary between live experiments and offline
evaluation data.

## Capture lifecycle

A bundle records baseline, injection, propagation, mitigation, and recovery evidence. Each
evidence item preserves its source payload, normalized representation, observation timestamp,
clock offset, and provenance.

An interrupted capture is resumable and remains incomplete until all required phases are
present. Cleanup must restore both preflight health and SLO state. A failed cleanup marks the
bundle contaminated.

## Training and replay rules

Only complete bundles with successful cleanup are training-eligible. Incomplete or contaminated
bundles cannot enter training data.

Offline replay consumes normalized evidence only; it never calls the fault engine, Kubernetes,
or a live backend. Replay ordering is deterministic by timestamp and evidence ID. Bundle
fingerprints use canonical JSON.

## Retention and resume

Persist the bundle after every evidence append and lifecycle transition. A resumed run must
reuse the same bundle ID and append only new evidence IDs. Retention policy must preserve the
raw-to-normalized provenance chain for the configured period and record deletion events.

Required validation:

1. interrupt a capture during propagation
2. resume it and verify deterministic bundle fingerprint
3. run replay with network and cluster access disabled
4. verify failed cleanup produces contaminated status and training exclusion
