# ADR 0002: typed integration boundaries

- Status: Accepted
- Date: 2026-11-12
- Issue: #6

## Context

AegisSRE integrates with telemetry stores, knowledge sources, identity providers, model
runtimes, Kubernetes, and audit sinks. Unbounded SDK calls or model-generated commands would
make authorization, redaction, timeout, and rollback behavior difficult to verify.

## Decision

Every external integration is isolated behind a typed adapter. Adapter contracts include
schema version, provenance, authorization context, timeout, retry budget, redaction behavior,
and typed failure results. Cluster actions are exposed only as allowlisted typed operations.

## Consequences

This adds interface and contract-test work, but makes trust boundaries explicit, supports
backend replacement, and prevents the model from directly authorizing or executing operations.
