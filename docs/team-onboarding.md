# Team onboarding evidence

This document records the repository-side setup for Issue #3.

## Canonical identities

| Role | GitHub account | Repository |
| --- | --- | --- |
| Canonical owner | `guvvalakarthik` | `guvvalakarthik/aegis-sre` |
| Contributor | `trivedi2005` | `trivedi2005/aegis-sre` (personal fork) |

The canonical `main` branch remains in `guvvalakarthik/aegis-sre`. Contributors work on
task branches and submit pull requests to that repository.

## Fork and remotes

After the collaborator invitation is accepted and the personal fork is created, configure
the contributor checkout as follows:

```bash
git clone https://github.com/trivedi2005/aegis-sre.git
cd aegis-sre
git remote rename origin upstream
git remote add origin https://github.com/trivedi2005/aegis-sre.git
git fetch upstream
git switch --track -c main upstream/main
git remote -v
```

Expected remotes:

- `origin`: `trivedi2005/aegis-sre` for contributor branches
- `upstream`: `guvvalakarthik/aegis-sre` for canonical `main`

## Local commit identity

Each contributor must use their own verified GitHub email. Configure it locally, never
globally, and verify it before the first commit:

```bash
git config --local user.name "Trivedi"
git config --local user.email "VERIFIED_GITHUB_EMAIL"
git config --local user.name
git config --local user.email
```

Do not commit tokens, passwords, SSH keys, company identities, or another person's email.

## Task branch and onboarding PR

The Issue #3 onboarding branch is:

```text
karthik/01-team-onboarding
```

The branch is intentionally limited to this onboarding evidence. A contributor-created
no-op validation branch should be opened from the personal fork after access and remotes
are verified:

```bash
git fetch upstream
git switch -c trivedi/01-team-onboarding upstream/main
git commit --allow-empty -m "chore: verify contributor onboarding"
git push -u origin trivedi/01-team-onboarding
gh pr create --repo guvvalakarthik/aegis-sre \
  --base main \
  --head trivedi2005:trivedi/01-team-onboarding \
  --title "chore: verify contributor onboarding"
```

## Completion evidence

- [x] Canonical repository and contributor username recorded.
- [ ] Write collaborator invitation accepted by `trivedi2005`.
- [ ] Personal fork visible at `trivedi2005/aegis-sre`.
- [ ] Contributor remotes captured with `git remote -v`.
- [ ] Both local commit identities verified without exposing email or tokens.
- [ ] Contributor no-op onboarding PR passes CI and is reviewed by Karthik.

The unchecked items require actions in the contributor's GitHub account or checkout and
must be completed with real evidence; this document does not claim those actions occurred.
