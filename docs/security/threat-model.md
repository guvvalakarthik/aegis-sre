# AegisSRE v1 threat model

## Assets and trust zones

- **A1 — operational evidence:** logs, metrics, traces, events, runbooks, and code metadata.
- **A2 — credentials and policy:** identity tokens, Kubernetes permissions, and approval state.
- **A3 — control actions:** diagnostics, fault injection, remediation, rollback, and deployment.
- **A4 — audit evidence:** decisions, prompts metadata, tool calls, outcomes, and metrics.

Trust decreases across these zones:

1. authenticated operator and policy provider
2. typed control plane and adapters
3. external telemetry, retrieved documents, model output, and tool output
4. workload and cluster side effects

## Threat register

| ID | Threat | Impact | Required control | Tracking |
| --- | --- | --- | --- | --- |
| TM-01 | Prompt injection in logs or runbooks | policy bypass or unsafe action | treat content as data; isolate instructions; safety gate | #11, #29 |
| TM-02 | Telemetry poisoning | incorrect diagnosis and remediation | provenance, freshness, cross-signal consistency, abstention | #8, #9, #54 |
| TM-03 | Privilege escalation or confused deputy | unauthorized cluster change | caller RBAC, scoped service identity, typed allowlist | #11, #12 |
| TM-04 | Data leakage through prompts or logs | exposure of secrets or private evidence | redaction before persistence and context construction | #9, #27 |
| TM-05 | Unsafe remediation or retry storm | outage expansion | dry-run, approval, timeout, idempotency, rollback, kill switch | #11, #12 |
| TM-06 | Stale or cross-environment evidence | wrong target or historical decision | validity windows, environment filters, versioned provenance | #9, #28 |
| TM-07 | Model supply-chain compromise | malicious or incorrect actions | signed/versioned artifacts, isolated inference, benchmark gate | #50, #54 |
| TM-08 | Audit tampering or omission | non-repudiation failure | append-only events and reconciliation checks | #54 |
| TM-09 | Denial of service and resource exhaustion | unavailable diagnosis/control plane | quotas, bounded fan-out, timeouts, circuit breakers | #12, #50 |
| TM-10 | Malicious deployment/configuration metadata | misleading causal attribution | signed metadata and independent corroboration | #10, #28 |

## Safety invariants

- No model receives raw shell, cluster-admin credentials, or unrestricted network access.
- No action executes without an authenticated caller and an independent policy decision.
- No evidence is shown to a caller before authorization filtering.
- No failed, timed-out, or cancelled action skips cleanup and audit emission.
- No release is promoted without reproducible tests, security review, and known limitations.

## Residual risk

The v1 system may abstain during backend outages, incomplete telemetry, conflicting evidence,
or unknown incident classes. It does not guarantee root-cause correctness. Human approval
remains mandatory for high-impact operations until generated evaluation evidence supports a
narrower policy.
