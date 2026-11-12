# Typed agent runtime protocol

Incidents advance only through an explicit state transition table. Every transition, tool start,
completion, failure, and budget event is checkpointed. Restart recovery restores state, counters,
events, idempotency results, and circuit-breaker state.

Tools require a typed validator, explicit allowed roles and permissions, and an idempotency key.
Shell, cluster-admin, and unrestricted permissions are rejected. Outputs and checkpoint events
are redacted before persistence. Repeated idempotent calls return the committed result without
repeating the handler.

Budgets cover tokens, elapsed tool calls, retries, and total tool count. The runtime supports
bounded retries and opens a circuit breaker after repeated failures. Real persistent storage,
clock-enforced wall-time cancellation, and per-tool permission audit still require integration
with the S-05 runtime and deployment environment.
