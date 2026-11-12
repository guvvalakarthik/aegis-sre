# Operator dashboard protocol

The dashboard reads typed incident snapshots from a store boundary; it never accesses model or
agent runtime internals directly. Responses include incidents, evidence, trajectories, remediation
status, and audit records through stable Pydantic API models.

Authentication is supplied by an application authenticator and every store operation receives the
principal. Approval requires approver/admin roles; remediation requests require operator,
approver, or admin roles. Sensitive strings are redacted before response serialization.

Backend outages return a degraded 503 response rather than fabricated dashboard state. Replay
validation, role-boundary tests for every endpoint, real authentication integration, and live
telemetry/topology adapters remain required deployment validation.
