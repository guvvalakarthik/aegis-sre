# Incident dataset v1 integration gate

Issue #17 freezes one immutable manifest for ML, DL, transformer, RAG, and agent evaluation.

## Manifest requirements

The manifest records:

- dataset version and generation time
- source-manifest and quality-report hashes
- schema versions, split hash, and scenario versions
- provenance hashes
- at least 25 root-cause labels
- excluded and contaminated run counts

A manifest fingerprint is computed from canonical JSON. Rebuilding from the same source and
experiment manifests must reproduce the same fingerprint.

## Approval gate

The gate rejects contaminated runs, missing benchmark subsets, duplicate subset split hashes,
and fewer than 25 root-cause labels. Approved subsets must record their split hash, labels, and
evaluation protocol.

The gate does not fabricate missing metrics or mark a dataset approved. Both contributors
must independently rebuild the manifest, review excluded/failed runs, and record approval in
the pull request and dataset card.

## Limitations to document

Every dataset card must state class imbalance, missing or unavailable telemetry, excluded and
contaminated runs, scenario coverage, label latency, privacy/retention constraints, and
unsupported incident classes.
