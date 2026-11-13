---
name: pr
description: "Handle pull-request-only GitHub workflows through bundled scripts. Use to create, inspect, update, or check a PR; route landing through pr-merge."
---
# PR

## Required skills

Load `git` for repository state and branch pushes, then `github` for GitHub mechanics. Load `commit` when local changes remain, `pr-merge` for landing, or `ship` for the complete commit-to-merge workflow. Do not reload a skill that delegated to `pr`.

Use the wrapper; it delegates every GitHub operation to the repository-owned `github` script:

```bash
bash scripts/pr.sh preflight
bash scripts/pr.sh view [pr]
bash scripts/pr.sh checks [pr]
bash scripts/pr.sh create --confirm <title> <body-file> <base> <head>
bash scripts/pr.sh edit --confirm <pr> <title> <body-file>
```

Use only after commits exist. Use native Git for repository inspection and branch pushes, following the `git` skill's policies. Refuse creation from the default branch. Confirm repository, intended base/head, committed diff, and explicit approval for remote mutations. Preserve PR templates, issue references, and useful reviewer context.

For merge requests, load `pr-merge`; use `ship-asap` only when explicitly
requested. This wrapper intentionally exposes no merge command so approved
landing workflows own the complete cleanup sequence.

Use `commit` when local changes remain and `ship` for the complete commit-to-merge lifecycle. Report the canonical PR URL, action, current state, and blockers.
