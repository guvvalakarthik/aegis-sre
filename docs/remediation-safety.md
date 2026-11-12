# Remediation safety controller protocol

The safety controller is independent from the proposing model. It makes decisions only from the
typed action request, static policy, actor roles, and authenticated approval. Proposal text is
not included in the authorization digest and cannot alter permissions.

Actions must be allowlisted by operation, target, and environment. High-risk classes require an
unexpired HMAC approval from an approver role. Execution always follows dry-run, canary, apply,
and health-gate phases. Failed health gates trigger rollback; rollback failure escalates.

The controller has a deny-by-default kill switch and immutable hash-chained audit records. Real
sandbox isolation, adversarial authorization/race/replay testing, and independent safety review
remain required deployment validation; this module does not claim zero unsafe executions without
that suite.
