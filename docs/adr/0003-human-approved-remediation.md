# ADR 0003: human-approved remediation

- Status: Accepted
- Date: 2026-11-12
- Issue: #6

## Context

Diagnosis is probabilistic and operational actions can cause irreversible impact. A model
output is untrusted evidence, not an authorization decision.

## Decision

The control plane separates diagnosis, policy evaluation, approval, execution, and audit.
High-impact actions require explicit authenticated approval. All actions are allowlisted,
scoped, idempotent where possible, bounded by timeout and concurrency limits, and paired with
rollback or cleanup behavior. Uncertainty, missing evidence, policy failure, or backend
failure results in abstention.

## Consequences

Automation is slower for risky operations, but the system has a reviewable safety boundary
and a clear path to measured, narrow automation as evaluation evidence improves.
