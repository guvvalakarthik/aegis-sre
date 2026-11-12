# C4 context

AegisSRE is a safety-gated reliability platform. It consumes operational evidence, builds
bounded hypotheses, and proposes or executes only typed, authorized actions.

~~~mermaid
flowchart LR
  operator[Operator] -->|questions, approvals| aegis[AegisSRE]
  aegis --> telemetry[Telemetry backends]
  aegis --> knowledge[Versioned knowledge and runbooks]
  aegis --> cluster[Kubernetes workload]
  aegis --> identity[Identity and policy provider]
  aegis --> repo[Code and deployment metadata]
  aegis --> audit[Audit and metrics sink]
~~~

## External systems

| System | Direction | Trust | Boundary |
| --- | --- | --- | --- |
| Operator | in/out | authenticated but fallible | typed API, RBAC, approval state |
| Telemetry backends | in | untrusted | versioned adapters, schema validation, redaction |
| Knowledge/runbooks | in | untrusted | ACL-filtered retrieval and provenance |
| Kubernetes | out/in | high impact | allowlisted typed tools, dry-run, timeout, audit |
| Identity/policy | in | authoritative | short-lived identity and policy decision |
| Code/deployment metadata | in | untrusted | signed/versioned metadata adapter |
| Audit sink | out | operational record | append-only event contract |

The model and retrieved text never cross directly into Kubernetes credentials, shell execution,
or policy decisions.
