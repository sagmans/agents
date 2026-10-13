# agents
Agents, skills, plugins, configurations and more

## Git hooks

Checks run in tracked local Git hooks instead of push/PR CI. Run `scripts/setup-hooks` once after cloning; it points this clone's `core.hooksPath` at `.githooks`. Each hook runs the generic checks first (sign-off and commit message format, a gitleaks secret scan, and signed, signed-off commits on push), then this repository's checks in `.githooks/<hook>.d/` in name order. Install [gitleaks](https://github.com/gitleaks/gitleaks) first. Every check must pass before you push; never use `--no-verify`. Pre-push checks test exactly each pushed commit: in place only when it is the clean, unmodified checkout, otherwise in a temporary worktree of that commit.

This repository's checks:

- `pre-commit`: staged whitespace and conflict-marker check.
- `pre-push`: generic checks only (no project checks yet).
