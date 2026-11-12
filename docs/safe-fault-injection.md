# Safe fault-injection protocol

The injector accepts only the aegis-lab cluster and namespace, bounded targets, durations, blast
radius, and non-negative parameters. It supports pod kill, network delay/loss/partition, CPU and
memory stress, DNS failure, and disk pressure through typed adapter methods.

A cleanup journal is registered before apply and removed only after rollback or an apply failure.
A restarted controller can scan expired entries and force rollback, preventing process crashes from
leaving faults active. Active injection quotas and target overlap checks prevent cascading faults.

Real Kubernetes/Chaos Mesh adapters must prove namespace, cluster, quota, and host isolation in
the testbed. This PR provides the fail-closed controller and recovery contract without claiming
live cleanup evidence.
