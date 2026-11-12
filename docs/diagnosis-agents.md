# Staged diagnosis protocol

The workflow requires triage and an explicit evidence plan before any tool call. Only approved
read-only tools may collect evidence, and each query must be in the plan. Idempotency keys prevent
duplicate calls and a bounded tool budget terminates collection.

Competing hypotheses preserve supporting and refuting evidence IDs. A critic must review hypotheses
before finalization. Root causes include confidence, uncertainty, affected services, and exact
evidence citations. Unsupported or uncited conclusions produce an abstention report.

The implementation is model/provider-neutral. Real T-12 runtime integration, Top-1/Top-3 RCA,
coverage, latency, cost, and staged-vs-single-agent evaluation remain required validation.
