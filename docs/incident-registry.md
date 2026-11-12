# Incident scenario registry

Issue #11 defines scenario.v1 as the only accepted input to the experiment runner.

## Required scenario metadata

Each scenario declares:

- allowlisted target service and namespace
- one typed operation and maximum duration
- health and capacity preconditions
- expected telemetry and ground truth
- remediation approval, rollback operation, and attempt limit
- cleanup actions
- workload, chart, commit, and dataset versions
- deterministic seed and schema version

Unknown fields are rejected. A scenario that omits health or capacity preconditions is
invalid before any cluster call is made.

## Safety envelope

The default envelope permits only the aegis-lab namespace, a small service allowlist, and
typed fault operations. It limits duration to five minutes and requires remediation approval.
Invalid, excessive, or out-of-scope scenarios fail closed with a validation error.

The runner must perform these checks before acquiring credentials or invoking Kubernetes:

1. validate scenario schema
2. validate the safety envelope
3. verify the current cluster context is the disposable testbed
4. run health and capacity preflight checks
5. acquire a concurrency lock for the target
6. record the experiment identity and versions
7. execute only the typed operation

## Reproducibility

Experiment IDs are derived from scenario ID, seed, and canonical scenario fingerprint.
Runs record the tool version, start time, scenario fingerprint, and status. A registry change
requires a schema-versioned review and regenerated contract evidence.
