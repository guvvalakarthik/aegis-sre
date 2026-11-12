# Topology, load profiles, and SLOs

Issue #10 defines deterministic primitives for the telemetry testbed.

## Topology and change correlation

Topology edges carry environment, validity windows, evidence IDs, confidence, and whether the
edge was inferred. Queries must select edges active at the incident timestamp; current
topology must not be substituted for historical topology.

Deployment and configuration changes are represented as typed ChangeEvent records. A bounded
correlation window can filter changes by incident time, service, and environment while
preserving deterministic ordering.

## Load profiles

| Profile | Seed | Duration | Rate | Checkout ratio | Fault |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline | 1001 | 300 s | 10 rps | 10% | none |
| burst | 1002 | 180 s | 50 rps | 15% | none |
| checkout-heavy | 1003 | 300 s | 20 rps | 70% | none |
| degradation | 1004 | 300 s | 20 rps | 40% | dependency-latency |

The profiles are definitions, not fabricated run results. A runner must use the recorded seed
and persist generated request counts, timestamps, environment, workload version, and outcome.

## SLO calculations

SLO functions calculate from raw aggregates or sorted latency samples:

- availability is successful requests divided by total requests
- error rate is failed requests divided by total requests
- latency uses a deterministic percentile
- saturation, detection latency, and recovery time use upper-bound comparisons

The resulting report must include the exact Prometheus query or source record IDs so direct
query results can be compared with the generated report.
