# Data-flow and trust boundaries

~~~mermaid
sequenceDiagram
  participant O as Operator
  participant A as API
  participant E as Evidence
  participant M as Model gateway
  participant P as Safety gate
  participant T as Typed tool
  participant K as Kubernetes

  O->>A: authenticated question
  A->>E: authorized evidence query
  E-->>A: redacted evidence with provenance
  A->>M: bounded prompt and evidence
  M-->>A: hypothesis, citations, confidence
  A->>P: proposed action plus evidence
  P-->>A: deny, request approval, or allow
  A->>T: typed allowlisted operation
  T->>K: scoped API request
  K-->>T: observed result
  T-->>A: result, rollback state, audit event
  A-->>O: explanation and outcome
~~~

## Invariants

1. Untrusted input is labeled before it enters evidence, prompts, or policy evaluation.
2. Retrieval applies authorization and environment filters before model context construction.
3. Models can propose hypotheses and typed actions but cannot authorize or execute them.
4. Remediation requires an allowlisted operation, caller authorization, policy approval, bounded
   duration, and an audit record.
5. Every external call has a timeout, bounded retry policy, and typed failure result.
6. Secrets are resolved at the integration boundary and never placed in prompts, logs, or evidence.
7. The default action is abstention when evidence is missing, conflicting, stale, or unauthorized.

## Non-functional objectives

| Objective | v1 target | Measurement |
| --- | --- | --- |
| API availability | 99.0% monthly in staging | health and request metrics |
| Read-path latency | p95 <= 2 s excluding model provider | request histogram |
| Safety decision latency | p95 <= 500 ms | policy decision histogram |
| Remediation timeout | <= 60 s per operation | tool audit events |
| Audit completeness | 100% of model/tool/policy transitions | event reconciliation |
| Recovery | rollback attempt within 30 s of failed action | incident timeline |
| Cost | report per incident and model version | usage and billing adapter |
| Privacy | zero secrets in persisted records | redaction tests and scans |

These are initial budgets. Each later milestone must replace assumptions with generated
measurements and document deviations.
