# Ground-truth and remediation metadata protocol

Each scenario label includes root cause, affected services, blast radius, severity, expected
remediation, recovery signals, symptoms, cascading effects, and evidence-linked timeline events.
Root cause is separate from symptoms and downstream effects.

Observed runs are compared with declared tolerances for cause, service recall, blast radius,
recovery signals, and timing. A label is not considered accurate until the observed run proves
all required dimensions.

Playbooks are linked to a scenario and root cause and require typed actions, preconditions,
rollback steps, validation signals, and identified test runs. This PR provides the schema and
comparison logic; five-scenario telemetry runs and the generated label/playbook catalog remain
required validation.
