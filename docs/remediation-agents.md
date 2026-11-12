# Remediation and postmortem protocol

A remediation plan is valid only when its operation is allowlisted for the diagnosed cause and
contains preconditions, expected effect, risk, canary scope, validation criteria, and rollback.
Plans cannot execute before approval.

Command acceptance is not recovery. Verification requires health, SLO, telemetry, recurrence, a
timestamp, and evidence IDs. Failed verification invokes the registered rollback; rollback
failure produces escalation rather than a false recovery.

Postmortems distinguish evidence-linked facts and inferences from recommendations. Real replay of
successful, ineffective, harmful, and partial remediations, plan correctness, and factual-support
scores require K-09/T-13 integration artifacts and CI validation.
