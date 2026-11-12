# Incident-lab integration gate

The lab manifest freezes scenario catalog, ground truth, feature schema, dataset hash, quality report,
and environment versions. Each scenario evidence record requires a clean environment, reproduction
hash, ground-truth match, quality status, and machine-generated non-negative metrics.

Failed or inconclusive reproductions remain visible. Quality exceptions are allowed only when
limitations are documented, and known gaps/OOD scenarios are mandatory. Modeling readiness requires
all scenario reproductions to pass, ground truth to match, and independent approvals from both
contributors against the same manifest.

The actual clean-environment reruns, scenario catalog, quality report, and published lab evidence
must be generated from K-07 through K-12 integrations; this contract does not fabricate readiness.
