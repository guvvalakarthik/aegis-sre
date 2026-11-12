# Benchmark v1 protocol

Benchmark results are immutable evidence records tied to one benchmark version, dataset version,
split hash, evaluation version, and common incident-window definition. Every result requires a
machine-generated artifact URL. Failed and inconclusive results remain in the report.

Champion selection is blocked until two independent contributor approvals exist and the candidate
meets declared latency, memory, and cost budgets. Quality alone cannot select a model. The report
must include confidence intervals, false-alarm intervention impact, negative results, OOD and
rare-incident weaknesses, and a clean-environment reproduction record.

The contract rejects mismatched lineage, duplicate model/task rows, non-finite metrics, missing
operational evidence, and invalid approvals. It does not fabricate benchmark outputs; real model
runs must populate the report before Issue #25 can be considered complete.
