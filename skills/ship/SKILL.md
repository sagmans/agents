---
name: ship
description: "Ship completed repository work: owned repositories that are not forks push signed commits straight to main; forks and external repositories go through pull request creation, squash merge, and automatic post-merge cleanup. Use when user says ship, release this change, open and merge PR, or wants finished code delivered via GitHub."
---
# Ship

## Route by ownership

Read `git remote get-url origin` and check `GIT_TRUNK_OWNERS` or `git config --get-all agents.trunkOwners` alongside the fork check from the `git` skill.

- Owned repository: the `origin` owner matches a configured trunk owner and `gh repo view "$(git remote get-url origin)" --json isFork --jq .isFork` prints `false`. Name `origin`: a bare `gh repo view` reads `upstream` in fork clones. Any other output or an error means not owned. Follow [Owned repositories: trunk flow](#owned-repositories-trunk-flow) and stop there.
- External repository, including a fork even under a configured owner: follow the PR flow in the rest of this skill. Push only with user approval, as the `git` skill requires.

## Owned repositories: trunk flow

Local hooks are the only gate before `origin`, so every step runs in full.

1. Commit each logical group on `main` through the `commit` skill.
2. `git fetch origin`, then `git rebase origin/main`. Resolve conflicts, then rerun the tests.
3. Review the full outgoing change: `git log -p origin/main..main`. Check correctness, security, secrets, and attribution.
4. Run the project's tests and checks. Dogfood the change as an end user and collect proof.
5. Do not ask for push approval when local hooks are green; escalate only a critical decision or ambiguity.
6. `git push origin main`. The `pre-push` hook runs the full gate. When it fails, fix the cause in a new commit and repeat from step 2.

Done when `origin/main` equals local `main`, the hooks passed, and the report lists commits, checks, and proof.

## Overview

Ship to an external repository means finish current repo work through Git only:

1. commit all changes, atomically, group by group
2. push branch to `origin`
3. create PR
4. validate PR readiness: checks, reviews, comments, threads, activity
5. squash-merge PR via `gh pr merge --squash`
6. automatically clean merged worktree and branches, then report each result

## Required Skills

Before starting, load the workflow owners in this order:

- `git` for repository inspection, branch, worktree, fetch, and push operations
- Native Git, as directed by `git`, when work must move off the default branch into a fresh branch or worktree. There is no branch helper to load.
- `commit` for atomic GPG-signed and Signed-off commits
- `github` and `pr` for GitHub PR creation and inspection
- `pr-merge` for the readiness gate, squash merge, and automatic post-merge cleanup

`pr-merge` loads `pr-digest`, CI, review-comment, and conflict helpers when needed. Do not reload `ship` from a dependency.

## When to Use

Use when user asks to:

- "ship" current work
- push, PR, and merge completed changes
- deliver finished code through GitHub
- convert local repo changes into merged upstream changes
- automatically clean merged worktree and branches after merge

## When Not to Use

Do not use when:

- work is not complete or tests fail
- repo has unrelated/user-owned changes you cannot safely classify
- external repository whose current branch is the default branch, with no feature branch or worktree created yet
- remote host is not GitHub
- user only asks for planning/review, not delivery

Clarify before proceeding when change ownership, target branch, merge strategy, remote host, or default branch is ambiguous.

## Workflow

### 1. Preflight

- Inspect branch and status:
  - `git status --short --branch`
  - `git branch --show-current`
  - `git remote get-url origin`
- Never modify git config.
- In external repositories, never work directly on default branch (`main`/`master`). If on default branch, create separate feature worktree/branch before editing or committing.
- Identify changed files by logical group. Exclude unrelated/user-owned changes unless user explicitly includes them.
- Run relevant tests/checks before PR creation when available.

### 2. Commit atomically

Use the `commit` skill (`scripts/commit.sh`) for each logical group:

```bash
bash scripts/commit.sh "type(scope): concise message" --body "why this change exists" -- <path>...
```

Verify no intended changes remain uncommitted:

```bash
git status --short
```

### 3. Push to origin

Push current feature branch to `origin`:

```bash
git push -u origin HEAD
```

### 4. Create PR

Detect host from `origin` URL, then use the `github` skill (`scripts/gh-pr.sh create` or `gh pr create`):

- GitHub: use the `github` skill to open the PR and record its URL/index

### 5. Validate PR readiness

Use `github` skill.

Before any merge action, all PR activity must be checked and settled:

- confirm PR URL/index
- confirm PR diff contains only intended commits/files (no unrelated changes)
- confirm branch up to date with base or explicitly document why not
- confirm mergeable (no conflicts)
- wait for required checks to finish; merge only when required checks green (or explicitly documented exception)
- confirm all requested reviews finished (no "changes requested" outstanding)
- triage PR activity: new comments since last check, any open review requests, any ongoing agent/bot reviews
- resolve all PR threads/conversations; do not merge with unresolved threads unless explicitly approved and documented
- final refresh immediately before merge: confirm no new commits pushed, checks still green, no new threads/comments opened
- record feature branch name, base/default branch, and whether current checkout is a temporary worktree

### 6. Merge PR and clean up

Use `pr-merge`. It owns the readiness gate, squash merge, and cleanup sequence.
Immediately after `gh pr merge --squash` succeeds, `pr-merge` must run the
`git` skill's `scripts/cleanup-after-merge.sh` once with the merged branch,
default branch, confirmed PR-head OID, and remote. Do not run a second generic
cleanup from `ship`. The helper removes the linked worktree or cleans and
reuses the primary, deletes local and remote branches, then switches/pulls the
default branch.

Report the script's discarded local entries, worktree, local-branch,
remote-branch, default-switch/pull, and final results. A nonzero exit is a
shipping blocker; report incomplete cleanup/update rather than replacing
failed Git cleanup with manual commands. If the worktree was removed or
reused, still run applicable repository-specific safety follow-ups even when
the default update failed.

## Verification / Exit Criteria

Owned non-fork repositories use the Exit Criteria in [Owned repositories: trunk flow](#owned-repositories-trunk-flow).
External repositories and forks are done only when:

- all intended changes are committed through the `commit` helper with signing, DCO, and separate subject/body arguments
- branch is pushed to `origin`
- PR exists and URL/index is known
- PR readiness gate completed: checks, reviews, comments, threads, and activity verified before merge
- PR is squash-merged
- post-merge cleanup script completed, or its exact blocker is reported
- merged worktree plus local and remote branches are absent
- default worktree is on the updated default branch
- applicable repository-specific post-merge instructions completed
- final status is clean or only explicitly unrelated user changes remain
- report lists commits, PR URL/index, merge result, cleanup operations, default-branch pull, tests/checks
