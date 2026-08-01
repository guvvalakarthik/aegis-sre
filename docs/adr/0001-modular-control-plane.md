# ADR 0001: Begin with a modular Python control plane

- Status: accepted
- Date: 2026-08-01

## Context

The target system contains telemetry ingestion, model inference, retrieval, workflow
orchestration, policy evaluation, and user-facing APIs. Prematurely deploying each module
as an independent service would add operational complexity before workload and scaling
boundaries are measured.

## Decision

Begin with one typed Python distribution organised by bounded context. Keep external
integrations behind interfaces and keep compute-heavy training outside the API process.
Split a component into a separately deployed service only when scaling, isolation, or
availability measurements justify it.

## Consequences

Local development and transactional changes remain straightforward. Module boundaries
must be enforced through reviews and static analysis. Model training and high-volume
telemetry processing will become separate workloads when introduced.
