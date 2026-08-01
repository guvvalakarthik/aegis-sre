# Contributing

## Workflow

1. Create an issue with explicit acceptance criteria.
2. Branch from `main` using `agent/<milestone>` for agent-authored work or
   `feat/<capability>` for contributor-authored work.
3. Keep the change scoped to one architectural capability.
4. Add executable tests for new behaviour. Do not add illustrative or placeholder tests.
5. Run formatting, linting, type checking, and tests locally.
6. Open a pull request that explains the behaviour, design trade-offs, and validation.

## Engineering standards

- Python code must be typed and pass strict mypy checks.
- Public modules, classes, and functions require concise docstrings when their contract is
  not obvious from the type signature.
- Configuration must come from environment-backed settings; secrets must not be committed.
- Logs must be structured and must not contain credentials or raw sensitive payloads.
- External integrations must be isolated behind typed interfaces.
- Safety decisions must fail closed.

## Commits

Use imperative, focused commit subjects. Avoid combining unrelated refactors and feature
work in one commit.
