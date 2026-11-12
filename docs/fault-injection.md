# Fault-injection engine

Issue #12 introduces a typed adapter boundary for registered Kubernetes incident actions.

## Safety properties

- The engine accepts an operation name and structured parameters, never model-generated shell.
- Unknown operations, empty targets, missing idempotency keys, and excessive timeouts fail closed.
- A non-blocking per-target lock prevents conflicting experiments.
- A process-wide kill switch stops new work and forces the current run toward cleanup.
- Dry-run records a plan without invoking an adapter.
- Repeated idempotency keys return the original result.
- Every run, apply, failure, and cleanup transition emits an audit event.
- Cleanup is attempted after a successful apply and is safe to call repeatedly by adapter contract.
- Unexpected adapter output is a failed, auditable result.

## Adapter contract

Each adapter implements typed apply and rollback methods. It must:

1. validate parameters against the registered operation schema
2. capture before-state before mutating a target
3. return a JSON-like state object
4. bound its own external calls
5. make rollback idempotent
6. avoid shell execution and unrestricted Kubernetes clients

The engine timeout bounds orchestration. It cannot forcibly terminate an already-running external
side effect, so adapters must also enforce request deadlines.

## Required validation

Run one real scenario for each adapter class, force interruption, verify cleanup, repeat cleanup,
and inspect the audit trail for the exact operation, target, state, error, and cleanup result.
