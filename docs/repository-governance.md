# Repository governance

This policy supports Issue #4. It applies to the canonical repository
https://github.com/guvvalakarthik/aegis-sre.

## Required branch policy

The main branch must be protected by a repository ruleset with:

- pull requests required; direct pushes and force pushes blocked
- at least one approval from a code owner
- stale approvals dismissed after new commits
- required CI checks from .github/workflows/ci.yml
- all review conversations resolved before merge
- task branches permitted
- branch deletion blocked for main
- emergency bypass limited to the repository owner and recorded in an incident

The ruleset is an administrator setting and cannot be encoded in repository files. After this
PR merges, configure it in Settings > Rules > Rulesets and capture the active ruleset
export or screenshot in the Issue #4 evidence.

## Contribution workflow

1. Open one issue using the appropriate feature, research, incident, or security template.
2. Create one focused task branch from main.
3. Add executable tests and acceptance evidence.
4. Open a PR using the repository template.
5. Obtain code-owner approval and pass CI.
6. Resolve all conversations and merge using the repository's selected squash policy.

Security reports should follow SECURITY.md and should not expose exploit details in public
issues.

## Emergency bypass

An emergency bypass is allowed only to contain an active incident or repair a broken
governance control. The owner must record the reason, affected commit, validation, rollback
plan, and follow-up issue. The bypass must not be used for ordinary feature delivery.
