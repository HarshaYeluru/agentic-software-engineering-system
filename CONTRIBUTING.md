# Contributing

## Branching strategy

This repo uses **trunk-based development**: `main` is always releasable, and all work happens on short-lived branches merged back via pull request. There is no long-lived `develop` branch.

Branch naming tells you who/what originated the change and what kind it is:

| Prefix | Used for | Example |
| --- | --- | --- |
| `agents/<topic>` | Changes authored by an AI coding agent (this repo's own subject matter) | `agents/ci-cd-integration-for-assignment` |
| `feature/<topic>` | New functionality, human-authored | `feature/expiry-support` |
| `fix/<topic>` | Bug fixes | `fix/redirect-404-on-expired-link` |
| `chore/<topic>` | Tooling, CI, docs, dependency bumps | `chore/add-lint-gate` |

Rules:

- Branch off the latest `main`.
- Keep branches short-lived — rebase or merge `main` back in if a branch lives more than a few days, rather than letting it drift.
- Squash-merge into `main` so the trunk history stays one commit per logical change; the PR description carries the detail the individual commits don't need to.
- Delete the branch after merge.

## Pull request process

1. Open a PR against `main` using the [PR template](.github/PULL_REQUEST_TEMPLATE.md) — it asks for the same shape of information this project's own workflow records for every engineering change: what changed, why, the risk level, and how it was validated.
2. CI (`.github/workflows/ci.yml`) must pass: unit tests, lint (`ruff`), security scan (`bandit`), and a dependency audit (`pip-audit`). Treat a red pipeline as a blocker, not a suggestion — this is exactly the "quality gate" the CI/CD design is meant to enforce.
3. At least one review approval is required before merge. Reviewers should treat the PR description's risk level the way the system's own `approval_required` gate treats a high-risk requirement: a `high` risk PR gets a closer read of the diff, not a rubber stamp.
4. CD (`.github/workflows/cd.yml`) runs automatically after CI succeeds on `main` and produces a smoke-tested build artifact — it is not a manual step you need to trigger.

## Code review practices

- Prefer small, single-purpose PRs — easier to review, easier to revert.
- If a PR touches `agentic_system/agents.py` or `orchestrator.py`, call that out explicitly in the description: these are the files that define what the agent decides and in what order, and deserve the most scrutiny.
- Run the full local check before opening a PR — this is exactly what CI runs, so there should be no surprises. See [docs/testing-approach.md](docs/testing-approach.md) for the commands and what each layer catches.
