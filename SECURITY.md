# Security policy

## Reporting

Do not open a public issue for a vulnerability. Report it privately through GitHub's
security advisory interface for this repository.

## Security model

AegisSRE treats telemetry, retrieved documents, model output, and tool responses as
untrusted input. Remediation is denied unless the requested operation is typed, explicitly
allowlisted, authorized for the caller, policy-approved, and auditable.

The language model is never granted an unrestricted shell or cluster-admin credentials.
Future remediation milestones must preserve this boundary.
