# C4 container view

~~~mermaid
flowchart TB
  api[API and authentication] --> orchestrator[Incident orchestrator]
  orchestrator --> evidence[Evidence service]
  evidence --> adapters[Typed integration adapters]
  adapters --> telemetry[(Telemetry stores)]
  adapters --> knowledge[(Knowledge store)]
  orchestrator --> diagnosis[Diagnosis and hypothesis service]
  diagnosis --> model[Model gateway]
  diagnosis --> policy[Policy and safety gate]
  policy --> tools[Typed remediation tools]
  tools --> cluster[Kubernetes API]
  orchestrator --> audit[Audit and metrics]
  api --> audit
~~~

## Container contracts

| Container | Responsibility | Must not do |
| --- | --- | --- |
| API/authentication | authenticate callers and enforce request shape | execute cluster actions |
| Incident orchestrator | coordinate bounded workflows and budgets | invent evidence or bypass policy |
| Evidence service | retrieve authorized, versioned evidence | return data outside caller ACL |
| Typed adapters | normalize external systems | expose raw credentials or shell |
| Diagnosis service | produce hypotheses with citations and abstention | authorize remediation |
| Model gateway | invoke versioned models with resource limits | access cluster or secrets |
| Policy/safety gate | evaluate authorization, risk, approval, and limits | accept model-only approval |
| Typed remediation tools | execute allowlisted operations with rollback | accept raw model-generated commands |
| Audit/metrics | record decisions, tool calls, and outcomes | store secrets or raw sensitive payloads |

Every adapter exposes a typed interface with explicit timeout, retry, provenance, and error
semantics. Unknown fields are preserved or quarantined according to the contract version.
