# Agent safety integration gate

The frozen manifest binds the agent graph, prompts, policy, tools, and model versions. Scenario
results are accepted only from clean environments and must prove zero unsafe actions. Every side
effect must have both authorization and audit provenance.

Read-only, low-risk, approval-required, and deny scenarios are represented explicitly. Abstention,
escalation, and policy denial cannot execute side effects. The gate keeps failure analysis but
redacts common secret forms before publication.

Two independent contributors must sign the same manifest and rationale before release. This
contract does not fabricate trajectory metrics or claim a release without the incident-lab
adversarial suite and independent clean-environment rerun.
