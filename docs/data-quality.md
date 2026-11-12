# Dataset quality and leakage prevention

Issue #15 defines a bounded dataset-row contract and machine-readable quarantine reasons.

## Required row fields

Every row has a dataset version, unique row ID, incident ID, split, service, observation time,
window bounds, label, numeric features, and explicit units. Unknown fields are rejected.

## Checks

The validator reports, without silently repairing data:

- duplicate row IDs
- observation timestamps outside declared windows
- empty feature maps
- NaN or infinite feature values
- an incident ID appearing in multiple incompatible splits
- overlapping windows for the same incident across splits

Invalid rows are quarantined with a stable reason code and detail. The source dataset remains
unchanged.

## Pipeline contract

Run the same validator on bounded CI fixtures and full pipeline data. Publish only the
dataset version, counts, reason-code summary, and pass/fail result; never publish private
telemetry or labels.

A quality report passes only when no issues are present. Known schema, duplication, and
leakage defects must be injected into fixtures to prove the checks fail closed.
