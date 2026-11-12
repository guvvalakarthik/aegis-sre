# Incident scenario protocol

Scenario manifests are typed, seeded, versionable, and restricted to the aegis-lab namespace.
They bound duration to fifteen minutes, target service names, blast radius, parameters, expected
symptoms, and recovery signals. Deterministic parameters derive from the recorded seed.

Runs have an explicit lifecycle: created, injected, stopped, cleaned, or failed. Ground truth
records injection, detection, recovery, and cleanup timestamps. Cleanup is mandatory and adapters
must implement it without host or other-cluster access.

The catalog covers pod crash, network latency/error, CPU stress, memory stress, DNS failure, and
dependency outage. Real Kubernetes adapters, twice-repeated telemetry/timing validation, scoped
cleanup proof, and generated SLO impact evidence require the K-06 testbed.
