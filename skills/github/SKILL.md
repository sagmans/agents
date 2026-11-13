---
name: github
description: "Operate GitHub pull requests through a safe bundled script for inspection, creation, editing, and checks. Route normal merges through pr-merge; ship-asap owns explicitly requested emergency landing."
---
# GitHub

## Related skills

Load `git` for repository state and branch mutations. Load `pr` for a PR workflow unless `pr`, `ship`, or `pr-merge` already delegated a GitHub operation here. Load `pr-merge` before landing an existing PR, or `ship` for the complete commit-to-merge workflow.

Use the bundled script instead of reconstructing `gh` commands:

```bash
bash scripts/github-pr.sh preflight
bash scripts/github-pr.sh view [pr]
bash scripts/github-pr.sh checks [pr]
bash scripts/github-pr.sh create --confirm <title> <body-file> <base> <head>
bash scripts/github-pr.sh edit --confirm <pr> <title> <body-file>
```

PR creation and editing require explicit user approval. Inspection is read-only. Use native Git for repository inspection and branch pushes, following the `git` skill's policies. Confirm repository, base/head, diff, checks, reviews, threads, and mergeability before mutation.

Mutation commands require exact `--confirm`, run preflight, and reject foreign-repository targets; creation also rejects the default head. This helper intentionally exposes no merge command. Load `pr-merge` for normal landing; use `ship-asap` only when explicitly requested. Both own complete cleanup after merging.

Never modify Git configuration or use admin, force, history-rewrite, or hook bypasses without separate explicit approval. Report the canonical PR URL, action, checks/review state, and blockers.
